from setuptools import setup


setup(
    name='client',
    version='1.0',
    test_suite='client.tests',
    entry_points={
        'console_scripts': [
            'chatclient = client.script:main'
        ]
    }
)
