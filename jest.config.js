const {pathsToModuleNameMapper} = require('ts-jest');
const {compilerOptions} = require('./tsconfig.json');

module.exports = {
  testEnvironment: 'node',
  rootDir: __dirname,
  moduleNameMapper: {
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': '<rootDir>/client/fileMock.js',
    ...pathsToModuleNameMapper(compilerOptions.paths, {prefix: '<rootDir>/'})
  }
};
