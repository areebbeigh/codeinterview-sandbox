import os

SANDBOX_DIR = os.path.abspath(os.path.dirname(__file__))

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
