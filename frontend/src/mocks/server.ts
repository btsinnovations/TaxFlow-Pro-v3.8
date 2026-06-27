import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/**
 * MSW server for Node.js (Vitest) and test environments.
 * This server is started in test setup and cleaned up after each test.
 */
export const server = setupServer(...handlers);