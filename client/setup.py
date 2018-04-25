from setuptools import setup

setup(
    name='client',
    version='1.0',
    description='Simple chat client written with Python asyncio.',
    url='https://github.com/worstof3/chat/client',
    author='Łukasz Karpiński',
    packages=['client'],
    test_suite='client.tests',
    entry_points={
        'console_scripts': [
            'chatclient=client.script:main'
        ]
    }
)
