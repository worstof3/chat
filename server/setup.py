from setuptools import setup


setup(
    name='server',
    version='1.0',
    test_suite='server.tests',
    entry_points={
        'console_scripts': [
            'chatserver = server.script:main'
        ]
    }
)
