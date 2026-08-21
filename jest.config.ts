import {Config} from '@jest/types';

const config: Config.InitialOptions = {
  testEnvironment: 'jsdom',
  rootDir: __dirname,
  setupFiles: ['<rootDir>/client/testSetup.js'],
  moduleDirectories: ['node_modules', '<rootDir>'],
  moduleNameMapper: {
    '\\.(png|svg)$': '<rootDir>/client/fileMock.js',
    '^../google/type/(.*)$': '<rootDir>/node_modules/@buf/googleapis_googleapis.bufbuild_es/google/type/$1'
  },
  collectCoverage: true,
  collectCoverageFrom: [
    '**/*.ts',
    '**/*.tsx',
    '!**/*.test.ts',
    '!**/*.test.tsx',
    '!**/BUILD',
  ],
  coverageReporters: ['text']
};

export = config;
