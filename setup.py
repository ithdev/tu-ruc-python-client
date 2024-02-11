from setuptools import setup, find_packages

setup(
    name='tu-ruc-python-client',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        'requests'
    ],
    author='Sebastian Alvarez',
    author_email='ca.sebastianlv@gmail.com',
    description='Cliente Python para la API de TURUC Paraguay ',
    url='https://github.com/seb5433/tu-ruc-python-client',
)
