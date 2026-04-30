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
} from "@mui/material";
import MailOutlineIcon from "@mui/icons-material/MailOutlined";

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

export default function SinglePost({ post }) {
  const [expanded, setExpanded] = useState(false);
  const authorName = post.user_name || "Unknown";

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
      </CardContent>

      <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
        <Button
          variant={expanded ? "outlined" : "contained"}
          size="small"
          onClick={() => setExpanded((v) => !v)}
          sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
        >
          {expanded ? "Show less" : "Read More"}
        </Button>
      </CardActions>
    </Card>
  );
}
