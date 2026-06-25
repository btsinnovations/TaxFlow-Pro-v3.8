import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock fetch globally for component tests that do not use the API hook.
globalThis.fetch = vi.fn();
