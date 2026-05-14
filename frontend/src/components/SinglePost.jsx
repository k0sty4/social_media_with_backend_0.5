import { useState } from "react";
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Box,
  Avatar,
  Divider,
  TextField,
  Alert,
} from "@mui/material";
import MailOutlineIcon from "@mui/icons-material/MailOutlined";
import EditIcon from "@mui/icons-material/Edit";
import { useAuth } from "../auth.jsx";
import { updatePost } from "../api";

function initials(name) {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function colorFromString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 60%, 55%)`;
}

export default function SinglePost({ post, onPostUpdated }) {
  const { user } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(post.title);
  const [body, setBody] = useState(post.body);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const authorName = post.user_name || "Unknown";
  const canEdit = user && user.id === post.user_id;

  function startEdit() {
    setTitle(post.title);
    setBody(post.body);
    setError(null);
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setError(null);
  }

  async function saveEdit() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePost(post.id, { title, body });
      onPostUpdated?.({
        ...post,
        title: updated.title,
        body: updated.body,
      });
      setEditing(false);
    } catch (err) {
      if (err.status === 401) {
        setError("Session expired. Please log in again.");
      } else if (err.status === 404) {
        setError("Post not found or you don't have access.");
      } else {
        setError(err.message || "Failed to save");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      elevation={2}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRadius: 3,
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: 6,
        },
      }}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
          <Avatar
            src={post.avatar || undefined}
            alt={authorName}
            sx={{
              bgcolor: colorFromString(authorName),
              width: 40,
              height: 40,
              fontSize: 14,
              fontWeight: 700,
            }}
          >
            {initials(authorName)}
          </Avatar>
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography variant="subtitle2" noWrap sx={{ fontWeight: 600 }}>
              {authorName}
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, color: "text.secondary" }}>
              <MailOutlineIcon sx={{ fontSize: 14 }} />
              <Typography variant="caption" noWrap>
                {post.email}
              </Typography>
            </Box>
          </Box>
        </Box>

        {editing ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            <TextField
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              size="small"
              fullWidth
            />
            <TextField
              label="Body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              size="small"
              fullWidth
              multiline
              minRows={3}
            />
            {error && <Alert severity="error">{error}</Alert>}
          </Box>
        ) : (
          <>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, lineHeight: 1.3, mb: 1.25 }}
            >
              {post.title}
            </Typography>

            <Divider sx={{ mb: 1.5 }} />

            <Typography
              variant="body2"
              color="text.primary"
              sx={{
                whiteSpace: "pre-line",
                lineHeight: 1.6,
                ...(expanded
                  ? {}
                  : {
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }),
              }}
            >
              {post.body}
            </Typography>
            {error && !editing && (
              <Alert severity="error" sx={{ mt: 1.5 }}>
                {error}
              </Alert>
            )}
          </>
        )}
      </CardContent>

      <CardActions sx={{ px: 2, pb: 2, pt: 0, gap: 1 }}>
        {editing ? (
          <>
            <Button
              variant="contained"
              size="small"
              onClick={saveEdit}
              disabled={saving || !title.trim() || !body.trim()}
              sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
            <Button
              variant="outlined"
              size="small"
              onClick={cancelEdit}
              disabled={saving}
              sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button
              variant={expanded ? "outlined" : "contained"}
              size="small"
              onClick={() => setExpanded((v) => !v)}
              sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
            >
              {expanded ? "Show less" : "Read More"}
            </Button>
            {canEdit && (
              <Button
                variant="text"
                size="small"
                startIcon={<EditIcon fontSize="small" />}
                onClick={startEdit}
                sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
              >
                Edit
              </Button>
            )}
          </>
        )}
      </CardActions>
    </Card>
  );
}
