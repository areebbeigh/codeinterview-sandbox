import os
import codecs
import uuid
import time
import logging
import shutil
from threading import Thread

import docker
from docker.types import Mount
from docker.errors import ImageNotFound, BuildError, APIError, NotFound

from sandbox import settings
from sandbox.settings import LANG_CONFIG

logger = logging.getLogger('sandbox')
# Not doing this causes a `LookupError: unknown encoding: ascii` in
# Sandbox.__del__ later on when logger.info() tries to open the log file
# TODO: investigate futher.
codecs.lookup('ascii')


def get_code_filename(language):
    assert language in LANG_CONFIG, 'Language not supported!'
    config = LANG_CONFIG[language]
    return f'code.{config["extension"]}'


def get_run_command(language,
                    code_filename=None,
                    input_filename='input.txt',
                    output_filename='output.txt'):
    assert language in LANG_CONFIG, 'Language not supported!'

    config = LANG_CONFIG[language]
    if not code_filename:
        code_filename = get_code_filename(language)

    rv = ['/bin/bash', '-c']
    run_cmd = config['compile'](code_filename)
    run_cmd.extend(['<', input_filename, '&>', output_filename])
    cmd_string = ' '.join(run_cmd)
    rv.append(cmd_string)
    return rv


class MemoryLimitExceeded(Exception):
    pass


class UnsupportedLanguage(Exception):
    pass


class TimeoutError(Exception):
    pass


class Sandbox:
    def __init__(self, time_limit=settings.DEFAULT_TIME_LIMIT,
                 memory_limit=settings.DEFAULT_MEMORY_LIMIT,):
        self.client = docker.from_env()
        self.id = str(uuid.uuid4())
        self.memory_limit = memory_limit
        self.execution_time = None
        self.time_limit = time_limit+1
        self.time_limit_exceeded = False
        self.memory_limit_exceeded = False
        self.events_stream = None
        self.event_listener_thread = None

        try:
            self.image = self.client.images.get(
                settings.DOCKER_IMAGE_FULL_NAME)
        except ImageNotFound:
            logger.info('Image %s not found. Builing...' %
                        settings.DOCKER_IMAGE_FULL_NAME)
            self.image = self.build_image()
            logger.info('Sandbox image built.')

        if not os.path.isdir(settings.USER_CODE_DIR):
            logger.info('Creating usercode directory...')
            os.mkdir(settings.USER_CODE_DIR)

        logger.info('New sandbox (%s) created' % self)

    def __repr__(self):
        return f'Sandbox<id: {self.id}, mem_limit: {self.memory_limit}, time_limit: {self.time_limit}>'

    def __del__(self):
        self.clean_up()

    # Container related helpers

    def build_image(self):
        try:
            return self.client.images.build(path=settings.DOCKERFILE_DIR,
                                            tag=settings.DOCKER_IMAGE_FULL_NAME,)
        except BuildError as e:
            logger.error(e)
            logger.error(e, exc_info=True)
            raise

    def create_container(self, cmd):
        usercode_mount = Mount(source=self.code_directory,
                               target='/home/',
                               type='bind',)
        logger.info('Runnning %s in container...' % cmd)
        try:
            if not settings.DOCKER_RUNTIME:
                logger.warn('No custom runtime given. Running in default Docker runtime')

            return self.client.containers.create(image=settings.DOCKER_IMAGE_FULL_NAME,
                                                runtime=settings.DOCKER_RUNTIME,
                                                 command=cmd,
                                                 mounts=[usercode_mount, ],
                                                 working_dir='/home/',
                                                 mem_limit=self.memory_limit,
                                                 network_disabled=True,
                                                 network_mode=None,
                                                 privileged=False,
                                                 detach=True,)
        except ImageNotFound as e:
            logger.error(e)
            logger.error(e, exc_info=True)
            raise
        except APIError as e:
            logger.error(e)
            logger.error(e, exc_info=True)
            raise

    @property
    def is_running(self):
        assert getattr(self, 'container', None), 'No active container yet.'
        return bool(self.client.containers.list(filters={
            'id': self.container.id
        }))

    def kill_container(self):
        if not self.is_running:
            return
        try:
            logger.info('Attempting to kill container...')
            self.container.kill()
            logger.info('Container killed')
        except Exception as e:
            logger.error('Could not kill container')
            logger.error(e)
            logger.error(e, exc_info=True)
            raise

    def remove_container(self):
        logger.info('Removing container...')
        try:
            self.client.containers.get(self.container.id)
        except NotFound:
            logger.info('Container already removed.')
            return

        if self.is_running:
            logger.info('Container is still running, killing...')
            self.kill_container()
        try:
            logger.info('Attempting remove...')
            self.container.remove()
            logger.info('Container removed')
        except Exception as e:
            logger.error('Could not remove container')
            logger.error(e)
            logger.error(e, exc_info=True)
            raise

    # Sandbox files

    @property
    def code_directory(self):
        return os.path.join(settings.USER_CODE_DIR, self.id)

    @property
    def code_file_path(self):
        return os.path.join(self.code_directory, self.code_filename)

    @property
    def input_file_path(self):
        return os.path.join(self.code_directory, self.input_filename)

    @property
    def output_file_path(self):
        return os.path.join(self.code_directory, self.output_filename)

    def clean_up(self, remove_code_dir=True):
        self.stop_threads()
        self.remove_container()
        if remove_code_dir and os.path.isdir(self.code_directory):
            logger.info('Deleting sandbox usercode folder')
            shutil.rmtree(self.code_directory)

    # Executing code

    def _event_listener(self):
        self.events_stream = self.client.events(
            decode=True,
            filters={'container': self.container.id})

        for event in self.events_stream:
            assert event['id'] == self.container.id
            logger.info(f"[DockerEvent] {event['id']}: {event['status']}")
            if event['status'] == 'oom':
                self.memory_limit_exceeded = True

    def start_event_listener(self):
        logger.info('Starting client event listener thread...')
        self.event_listener_thread = Thread(target=self._event_listener)
        self.event_listener_thread.start()

    def stop_threads(self):
        if self.events_stream:
            logger.info('Closing events stream...')
            self.events_stream.close()
        if self.event_listener_thread:
            logger.info('Stopping event_listener_thread...')
            self.event_listener_thread.join()

    def run(self, language, code, stdin):
        logger.info('Sandbox (%s) received run request' % self.id)
        assert not os.path.isdir(self.code_directory)

        os.mkdir(self.code_directory)
        logger.info('Created code directory %s' % self.code_directory)

        self.code_filename = get_code_filename(language)
        self.input_filename = 'input.txt'
        self.output_filename = 'output.txt'

        logger.info('Writing input code to %s' % self.code_file_path)
        with open(self.code_file_path, 'w') as f:
            f.write(code)
        logger.info('Writing stdin to %s' % self.input_file_path)
        with open(self.input_file_path, 'w') as f:
            f.write(stdin)

        command = get_run_command(language,
                                  self.code_filename,
                                  self.input_filename,
                                  self.output_filename)
        self.container = self.create_container(command)
        start_time = time.time()
        try:
            self._start_container()
            self.execution_time = round(time.time() - start_time, 2)
        except BaseException as e:
            logger.error('Container run error')
            logger.error(e)
            logger.error(e, exc_info=True)
            self.clean_up(remove_code_dir=False)
            raise

    def _start_container(self):
        self.start_event_listener()
        self.container.start()

        logger.info('Waiting for (max) %s seconds...' % self.time_limit)
        seconds = 0
        while self.is_running and seconds < self.time_limit:
            time.sleep(1)
            seconds += 1
        logger.info('Outside wait loop')

        try:
            if self.is_running:
                logger.info('Container status: %s. Killing container.' %
                            self.container.status)
                self.kill_container()
                self.time_limit_exceeded = True
        except APIError as e:
            logger.error(e)
            logger.error(e, exc_info=True)
            raise
        finally:
            self.remove_container()
            self.stop_threads()

        if self.memory_limit_exceeded:
            raise MemoryLimitExceeded('Memory limit exceeded')
        if self.time_limit_exceeded:
            raise TimeoutError('The code took too long to run')
