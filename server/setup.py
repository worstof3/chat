from setuptools import setup

setup(
    name='server',
    version='1.0',
    description='Simple chat server written with Python asyncio.',
    url='https://github.com/worstof3/chat',
    author='Łukasz Karpiński',
    packages=['server'],
    test_suite='server.tests',
    entry_points={
        'console_scripts': [
            'chatserver=server.script:main'
        ]
    }
)
