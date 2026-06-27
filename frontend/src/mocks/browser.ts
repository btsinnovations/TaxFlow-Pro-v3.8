import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/**
 * MSW worker for browser (dev mode).
 * This is enabled in main.tsx when import.meta.env.DEV is true.
 */
export const worker = setupWorker(...handlers);