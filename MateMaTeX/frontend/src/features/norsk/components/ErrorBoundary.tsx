"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: unknown): State {
    const message =
      error instanceof Error ? error.message : "En ukjent feil oppstod.";
    return { hasError: true, message };
  }

  componentDidCatch(error: unknown, info: { componentStack?: string }) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <main className="min-h-screen bg-bg flex items-center justify-center px-4">
          <div className="w-full max-w-md text-center space-y-4">
            <p className="text-4xl">⚠️</p>
            <h1 className="text-xl font-semibold text-stone-900">Noe gikk galt</h1>
            <p className="text-stone-500 text-sm">{this.state.message}</p>
            <button
              onClick={this.handleReset}
              className="btn-primary mt-4 px-6 py-2 text-sm"
            >
              Prøv igjen
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
