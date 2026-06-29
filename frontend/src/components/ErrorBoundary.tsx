import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary — catches unhandled React render errors and displays
 * a fallback UI instead of white-screening the entire application.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("[ErrorBoundary] Unhandled render error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: "2rem",
            backgroundColor: "#0f1117",
            color: "#e0c068",
            fontFamily: "system-ui, -apple-system, sans-serif",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: "1.5rem, marginBottom: 0.5rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#8a8a8a", marginBottom: "1.5rem" }}>
            An unexpected error occurred while rendering this page.
          </p>
          {this.state.error && (
            <pre
              style={{
                maxWidth: "600px",
                padding: "1rem",
                backgroundColor: "#1a1a2e",
                borderRadius: "6px",
                fontSize: "0.75rem",
                color: "#c0c0c0",
                overflow: "auto",
                marginBottom: "1.5rem",
              }}
            >
              {this.state.error.message}
            </pre>
          )}
          <button
            onClick={this.handleReload}
            style={{
              padding: "0.6rem 1.5rem",
              backgroundColor: "#e0c068",
              color: "#0f1117",
              border: "none",
              borderRadius: "4px",
              fontSize: "0.9rem",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}