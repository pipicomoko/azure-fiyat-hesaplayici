/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "node",
  testMatch: ["**/src/__tests__/**/*.test.js"],
  collectCoverageFrom: ["src/**/*.js", "!src/__tests__/**"],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
};
