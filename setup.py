# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name='truescrub',
    version='0.1.0',
    author='Trevor Caira',
    author_email='trevor@caira.com',
    packages=['truescrub', 'truescrub.updater'],
    package_data={
      'truescrub': ['htdocs/vendor/*.js', 'templates/*.html'],
      'truescrub.updater': ['*.ini'],
    },
    install_requires=[
      'Flask==1.0.0',
      'waitress==1.4.3',
      'trueskill==0.4.5',
      'pyzmq==19.0.0',
      'werkzeug==0.15.6',
    ],
    classifiers=[
      'Programming Language :: Python :: 3',
      'License :: OSI Approved :: MIT License',
      'Operating System :: OS Independent',
    ],
)

