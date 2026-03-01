import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="page" style={{ textAlign: 'center' }}>
          <h2>Что-то пошло не так</h2>
          <p className="page-sub">Произошла непредвиденная ошибка.</p>
          <button className="btn btn-ghost" onClick={this.handleReset}>
            Попробовать снова
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
