# codeinterview-sandbox

This is a simple docker based sandbox used to run arbritary untrusted code. 
Originally written for [codeinterview](https://github.com/areebbeigh/codeinterview-backend).

By default, this will run behind a celery worker (`celery -A run worker -l info`) but you can just as easily modify it
for use with another interface.

## How it works
You must already have [docker](https://docker.io) installed (and optionally [gVisor](https://gvisor.dev/docs/) for securing your kernel).
Sandbox creates (and later destroys) a new container for every run request. The container is created from the already 
built image `sandbox/Dockerfile` with all the supported languages and dependencies. 

The output of the code is written directly into `{USER_CODE_DIR}/<sandbox uuid>/output.txt` and deleted once the sandbox
is deleted (`__del__()`) by the garbage collector.

## Settings
The settings are defined in `sandbox/settings.py`:

```python3
# Time limit in seconds for every run
DEFAULT_TIME_LIMIT = 5
# Memory limit for every run
DEFAULT_MEMORY_LIMIT = '100m'
# Image will built from Dockerfile if it doesn't already exist
DOCKER_IMAGE_NAME = 'codeint-sandbox'
DOCKER_IMAGE_TAG = 'v1'
DOCKER_IMAGE_FULL_NAME = f'{DOCKER_IMAGE_NAME}:{DOCKER_IMAGE_TAG}'
DOCKERFILE_DIR = SANDBOX_DIR
# gVisor runtime or blank for default runtime
DOCKER_RUNTIME = 'runsc'

# Celery related config
CELERY_BROKER_URL = os.environ.get('REDIS_URL')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL')

# These are language specific compile and run configs.
LANG_CONFIG = {
    'python3.6': {
        'compile': lambda name: f'(python3.6 {name})'.split(' '),
        'extension': 'py'
    },
    'cpp': {
        'compile': lambda name: f'(g++ {name} && ./a.out)'.split(' '),
        'extension': 'cpp'
    },
    'java': {
        'compile': lambda name: f'(java {name})'.split(' '),
        'extension': 'java'
    },
    'javascript': {
        'compile': lambda name: f'(node {name})'.split(' '),
        'extension': 'js'
    }
}
USER_CODE_DIR = os.path.join(SANDBOX_DIR, 'user-code')
```

## Adding a language
Two files need to be modified to add a language - `sandbox/Dockerfile` and `sandbox/settings.py:LANG_CONFIG`.
- Add the instructions for installing all language dependencies in `sandbox/Dockerfile`
- Add the instructions to compile and run (in a single command) a code file in given language.

Eg for python:

- Add `apt-get install -y python3.6` to the dockerfile.
- And to the settings file:
```python3
LANG_CONFIG = {
    ...
    'python3.6': {
        # Runs as (python3.6 code.py) > output.txt in the container
        'compile': lambda name: f'(python3.6 {name})'.split(' '),
        'extension': 'py'
    },
}
```


## Example

```python3
from sandbox import Sandbox
code = "print('hello world!', input())"

s = Sandbox()
s.run('python3.6', code, 'xyz') # 'hello world! xyz' -> user-code/<uuid>/output.txt
```

Example AWS deployment config and scripts are provided in `example/`.

## Contributing
Start by creating an issue describing your suggestion/idea/bug and we can take it from there! :)

