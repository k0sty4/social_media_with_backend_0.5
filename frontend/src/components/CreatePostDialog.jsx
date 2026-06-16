// Modal for composing a new post: a title, a rich-text body, and an optional
// image. On success it hands the freshly-created post back to the parent so it
// can be prepended to the feed without a refetch.

import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  IconButton,
} from "@mui/material";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import CloseIcon from "@mui/icons-material/Close";
import RichTextEditor from "./RichTextEditor";
import { createPost } from "../api";
import { strip } from "../htmlText";

export default function CreatePostDialog({ open, onClose, onCreated }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function reset() {
    setTitle("");
    setBody("");
    setImage(null);
    setPreview(null);
    setError(null);
  }

  function handleClose() {
    if (saving) return;
    reset();
    onClose?.();
  }

  function pickImage(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImage(file);
    setPreview(URL.createObjectURL(file));
  }

  function clearImage() {
    setImage(null);
    setPreview(null);
  }

  // The body is HTML; strip tags to check there's actual text before posting.
  const bodyHasText = strip(body).length > 0;
  const canSubmit = title.trim() && bodyHasText && !saving;

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const post = await createPost({ title: title.trim(), body, image });
      onCreated?.(post);
      reset();
      onClose?.();
    } catch (err) {
      if (err.status === 401) {
        setError("Please log in to post.");
      } else {
        setError(err.message || "Failed to create post");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ fontWeight: 700 }}>Create a post</DialogTitle>
      <DialogContent dividers sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <TextField
          label="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          size="small"
          fullWidth
          autoFocus
        />

        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
            Body
          </Typography>
          <RichTextEditor value={body} onChange={setBody} placeholder="Share your thoughts… (bold, italic, links supported)" />
        </Box>

        <Box>
          <Button
            component="label"
            variant="outlined"
            size="small"
            startIcon={<PhotoCameraIcon />}
            sx={{ textTransform: "none" }}
          >
            {image ? "Change image" : "Add image"}
            <input hidden type="file" accept="image/*" onChange={pickImage} />
          </Button>
          {preview && (
            <Box sx={{ position: "relative", mt: 1.5, display: "inline-block" }}>
              <Box
                component="img"
                src={preview}
                alt="preview"
                sx={{ maxWidth: "100%", maxHeight: 220, borderRadius: 2, display: "block" }}
              />
              <IconButton
                size="small"
                onClick={clearImage}
                sx={{ position: "absolute", top: 4, right: 4, bgcolor: "rgba(0,0,0,0.55)", color: "white", "&:hover": { bgcolor: "rgba(0,0,0,0.75)" } }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
          )}
        </Box>

        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={saving} sx={{ textTransform: "none" }}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!canSubmit}
          sx={{ textTransform: "none", fontWeight: 600 }}
        >
          {saving ? "Posting…" : "Post"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
