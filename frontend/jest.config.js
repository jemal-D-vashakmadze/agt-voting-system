const nextJest = require("next/jest")({ dir: "./" });

module.exports = nextJest({
  testEnvironment: "jest-environment-jsdom",
});
