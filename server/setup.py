from setuptools import setup


setup(
    test_suite='server.tests',
    entry_points={
        'console_scripts': [
            'chatserver = server.script:main'
        ]
    }
)
