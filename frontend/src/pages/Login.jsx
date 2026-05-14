// /login route. If the user is already signed in we redirect to "/".
// Wrong credentials show the server-provided error inline; a 429 (rate
// limited) message flows through the same path because api.js attaches it
// to err.message.

import { useState } from "react";
import { useNavigate, Link as RouterLink, Navigate } from "react-router-dom";
import {
  Container,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Box,
  Alert,
  Link,
} from "@mui/material";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login({ email, password });
      navigate("/");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container maxWidth="sm" sx={{ py: 3 }}>
      <Typography variant="h4" fontWeight={700} sx={{ mb: 3 }}>
        Login
      </Typography>

      <Card>
        <CardContent>
          <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
            />
            <Button type="submit" variant="contained" size="large" disabled={busy}>
              {busy ? "Signing in..." : "Sign in"}
            </Button>
            {error && <Alert severity="error">{error}</Alert>}
            <Typography variant="body2">
              No account?{" "}
              <Link component={RouterLink} to="/register">
                Register
              </Link>
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
}
