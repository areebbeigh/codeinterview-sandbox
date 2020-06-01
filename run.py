import logging

from celery.app import Celery
from celery import shared_task

from sandbox import settings, Sandbox, UnsupportedLanguage, TimeoutError, MemoryLimitExceeded
from sandbox.settings import LANG_CONFIG

logging.basicConfig(filename='worker.log',
                    level=logging.DEBUG,
                    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',)

celery = Celery('coderunner-sandbox')
celery.config_from_object(settings, namespace='CELERY')


@shared_task(name='tasks.sandbox.run_user_code')
def run_user_code(language, code, stdin):
    error, error_msg, output = False, None, None
    sandbox = None

    try:
        if language not in LANG_CONFIG:
            raise UnsupportedLanguage(f'{language} is not supported')
        sandbox = Sandbox()
        sandbox.run(language, code, stdin)
    except Exception as e:
        error = True
        error_msg = f'[{e.__class__.__name__}] {e}'

    try:
        if not error:
            with open(sandbox.output_file_path, 'r') as f:
                output = f.read()
        else:
            output = ''
    except Exception as e:
        output = ''

    rv = {
        'error': error,
        'error_msg': error_msg,
        'output': output,
        'exec_time': sandbox.execution_time if sandbox else -1,
    }
    return rv

if __name__ == '__main__':
    s = Sandbox()
    s.build_image()