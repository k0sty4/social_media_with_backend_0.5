// /register route. POST /api/auth/register both creates the account and
// signs the user in (the server sets the session cookie on 201), so on
// success we just redirect to "/".

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

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
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
      await register({ name, email, password });
      navigate("/");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Container maxWidth="sm" sx={{ py: 3 }}>
      <Typography variant="h4" fontWeight={700} sx={{ mb: 3 }}>
        Register
      </Typography>

      <Card>
        <CardContent>
          <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Name"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              fullWidth
            />
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
              helperText="At least 8 characters"
            />
            <Button type="submit" variant="contained" size="large" disabled={busy}>
              {busy ? "Creating account..." : "Sign up"}
            </Button>
            {error && <Alert severity="error">{error}</Alert>}
            <Typography variant="body2">
              Already have an account?{" "}
              <Link component={RouterLink} to="/login">
                Sign in
              </Link>
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
}
