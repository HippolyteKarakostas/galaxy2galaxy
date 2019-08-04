"""Install galaxy2galaxy."""

from setuptools import find_packages
from setuptools import setup


setup(
    name='galaxy2galaxy',
    version='0.0.1rc',
    description='Galaxy2Galaxy',
    author='ML4Astro',
    url='http://github.com/ml4astro/galaxy2galaxy',
    license='Apache 2.0',
    packages=find_packages(),
    scripts=[
        'galaxy2galaxy/bin/g2g-trainer',
        'galaxy2galaxy/bin/g2g-datagen',
    ],
    install_requires=[
        'six',
        'tensorflow',
        'tensor2tensor',
        'tensorflow-datasets',
        'tensorflow-probability',
    ],
    extras_require={
        'tensorflow': ['tensorflow>=1.13.1'],
        'tensorflow_gpu': ['tensorflow-gpu>=1.13.1'],
        'tensorflow-hub': ['tensorflow-hub>=0.1.1'],
        'tests': [
            'absl-py',
            'pytest>=3.8.0',
            'mock',
            'pylint',
            'jupyter',
            'gsutil',
            'matplotlib',
            # Need atari extras for Travis tests, but because gym is already in
            # install_requires, pip skips the atari extras, so we instead do an
            # explicit pip install gym[atari] for the tests.
            # 'gym[atari]',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
    keywords='astronomy machine learning',
)