import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  List,
  ListItemButton,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Box,
  CircularProgress,
  Alert,
  Divider,
  Chip,
  Paper,
  TextField,
  InputAdornment,
} from "@mui/material";
import EmailIcon from "@mui/icons-material/EmailOutlined";
import SearchIcon from "@mui/icons-material/Search";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import { fetchUsers, searchUsers } from "../api";

export default function Users() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const timer = setTimeout(async () => {
      try {
        const data = query.trim() ? await searchUsers(query.trim()) : await fetchUsers();
        setUsers(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700}>
          Users
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {loading ? "Loading…" : `${users.length} ${users.length === 1 ? "member" : "members"}`}
        </Typography>
      </Box>

      <TextField
        fullWidth
        placeholder="Search by name or email…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        size="small"
        sx={{ mb: 2 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
        }}
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
          <CircularProgress />
        </Box>
      ) : users.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>
          No users found.
        </Paper>
      ) : (
        <Paper elevation={1} sx={{ borderRadius: 3, overflow: "hidden" }}>
          <List disablePadding>
            {users.map((u, idx) => (
              <Box key={u.id}>
                {idx > 0 && <Divider component="li" />}
                <ListItemButton
                  alignItems="flex-start"
                  onClick={() => navigate(`/users/${u.id}`)}
                  sx={{ py: 2, px: 2.5 }}
                >
                  <ListItemAvatar>
                    <Avatar src={u.avatar} alt={u.name} sx={{ width: 48, height: 48 }} />
                  </ListItemAvatar>
                  <ListItemText
                    sx={{ ml: 1, pr: 10 }}
                    primary={
                      <Typography variant="subtitle1" fontWeight={600}>
                        {u.name}
                      </Typography>
                    }
                    secondary={
                      <>
                        <Box
                          component="span"
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: "text.secondary",
                            mt: 0.25,
                          }}
                        >
                          <EmailIcon sx={{ fontSize: 14 }} />
                          <Typography component="span" variant="body2">
                            {u.email}
                          </Typography>
                        </Box>
                        {u.bio && (
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.secondary"
                            sx={{ mt: 0.5, display: "block" }}
                          >
                            {u.bio}
                          </Typography>
                        )}
                      </>
                    }
                  />
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      position: "absolute",
                      right: 16,
                      top: "50%",
                      transform: "translateY(-50%)",
                    }}
                  >
                    {typeof u.postCount === "number" && (
                      <Chip
                        label={`${u.postCount} posts`}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    )}
                    <ChevronRightIcon sx={{ color: "text.secondary" }} />
                  </Box>
                </ListItemButton>
              </Box>
            ))}
          </List>
        </Paper>
      )}
    </Container>
  );
}
