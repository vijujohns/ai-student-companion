import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      errorMessage: error?.message || "Unexpected UI error",
    };
  }

  componentDidCatch(error, errorInfo) {
    // Keep detailed stack in console for diagnosis while showing safe UI.
    console.error("UI crash captured by AppErrorBoundary", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-crash-screen" role="alert">
          <h2>Brain Teaser Academy hit an unexpected UI error</h2>
          <p>
            The page was protected from a white-screen crash. Please reload the app.
          </p>
          <p className="app-crash-screen__detail">{this.state.errorMessage}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
