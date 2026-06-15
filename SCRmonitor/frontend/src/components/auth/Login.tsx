import { useState } from "react";
import { InvalidTokenError, useAuth } from "../../stores/authStore";

export function Login() {
  const { login } = useAuth();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await login(token);
    } catch (err) {
      setError(
        err instanceof InvalidTokenError
          ? err.message
          : err instanceof Error
            ? err.message
            : "登录失败，请重试",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-gate">
      <section className="panel login-card">
        <div className="login-card-head">
          <p className="eyebrow">SCRmonitor</p>
          <h2>登录</h2>
          <p className="field-hint">请输入访问令牌（Access Token）以继续。</p>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>访问令牌</span>
            <input
              type="password"
              autoFocus
              autoComplete="off"
              spellCheck={false}
              value={token}
              placeholder="粘贴你的访问令牌"
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          <button type="submit" disabled={submitting || token.trim().length === 0}>
            {submitting ? "验证中…" : "登录"}
          </button>
        </form>
      </section>
    </div>
  );
}
