import { useEffect, useRef, useState } from "react";
import { useParams, Link as RouterLink } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Avatar,
  Paper,
  Grid,
  Button,
  CircularProgress,
  Alert,
  Divider,
  Stack,
  Chip,
  Link,
  Breadcrumbs,
} from "@mui/material";
import EmailIcon from "@mui/icons-material/EmailOutlined";
import PhoneIcon from "@mui/icons-material/PhoneOutlined";
import LanguageIcon from "@mui/icons-material/Language";
import BusinessIcon from "@mui/icons-material/BusinessOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SinglePost from "../components/SinglePost";
import { fetchUser, fetchUserPosts } from "../api";

const PAGE_SIZE = 10;

export default function UserDetail() {
  const { id } = useParams();
  const [user, setUser] = useState(null);
  const [userLoading, setUserLoading] = useState(true);
  const [userError, setUserError] = useState(null);

  const [posts, setPosts] = useState([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [postsError, setPostsError] = useState(null);

  useEffect(() => {
    setUserLoading(true);
    setUserError(null);
    fetchUser(id)
      .then(setUser)
      .catch((err) => setUserError(err.message))
      .finally(() => setUserLoading(false));
  }, [id]);

  const inFlight = useRef(false);

  async function loadNextPosts() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPostsLoading(true);
    setPostsError(null);
    try {
      const nextPage = page + 1;
      const data = await fetchUserPosts(id, nextPage, PAGE_SIZE);
      setPosts((prev) => {
        const seen = new Set(prev.map((p) => p.id));
        const fresh = data.items.filter((p) => !seen.has(p.id));
        return [...prev, ...fresh];
      });
      setPage(nextPage);
      setHasMore(data.has_more);
    } catch (err) {
      setPostsError(err.message);
    } finally {
      setPostsLoading(false);
      inFlight.current = false;
    }
  }

  useEffect(() => {
    setPosts([]);
    setPage(0);
    setHasMore(true);
    loadNextPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (userLoading) {
    return (
      <Container sx={{ py: 6, display: "flex", justifyContent: "center" }}>
        <CircularProgress />
      </Container>
    );
  }

  if (userError || !user) {
    return (
      <Container maxWidth="md" sx={{ py: 3 }}>
        <Alert severity="error">{userError || "User not found"}</Alert>
        <Button component={RouterLink} to="/users" startIcon={<ArrowBackIcon />} sx={{ mt: 2 }}>
          Back to users
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link component={RouterLink} to="/users" underline="hover" color="inherit">
          Users
        </Link>
        <Typography color="text.primary">{user.name}</Typography>
      </Breadcrumbs>

      <Paper elevation={1} sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Box sx={{ display: "flex", gap: 3, alignItems: { xs: "flex-start", sm: "center" }, flexDirection: { xs: "column", sm: "row" } }}>
          <Avatar src={user.avatar} alt={user.name} sx={{ width: 88, height: 88 }} />
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" fontWeight={700}>
              {user.name}
            </Typography>
            {user.username && (
              <Typography variant="body2" color="text.secondary">
                @{user.username}
              </Typography>
            )}
            {user.bio && (
              <Typography variant="body1" sx={{ mt: 1 }}>
                {user.bio}
              </Typography>
            )}
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Chip label={`${user.postCount ?? posts.length} posts`} size="small" color="primary" />
            </Stack>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Grid container spacing={2}>
          {user.email && (
            <Grid item xs={12} sm={6}>
              <ContactRow icon={<EmailIcon fontSize="small" />} label="Email" value={user.email} />
            </Grid>
          )}
          {user.phone && (
            <Grid item xs={12} sm={6}>
              <ContactRow icon={<PhoneIcon fontSize="small" />} label="Phone" value={user.phone} />
            </Grid>
          )}
          {user.website && (
            <Grid item xs={12} sm={6}>
              <ContactRow icon={<LanguageIcon fontSize="small" />} label="Website" value={user.website} />
            </Grid>
          )}
          {user.company && (
            <Grid item xs={12} sm={6}>
              <ContactRow icon={<BusinessIcon fontSize="small" />} label="Company" value={user.company} />
            </Grid>
          )}
        </Grid>
      </Paper>

      <Box sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          Posts
        </Typography>
      </Box>

      {postsError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {postsError}
        </Alert>
      )}

      <Grid container spacing={2}>
        {posts.map((post) => (
          <Grid item xs={12} md={6} key={post.id}>
            <SinglePost post={post} />
          </Grid>
        ))}
      </Grid>

      <Box sx={{ display: "flex", justifyContent: "center", mt: 3, mb: 2 }}>
        {postsLoading ? (
          <CircularProgress />
        ) : hasMore ? (
          <Button variant="contained" size="large" onClick={loadNextPosts}>
            Load More
          </Button>
        ) : posts.length > 0 ? (
          <Box sx={{ color: "text.secondary" }}>No more posts.</Box>
        ) : (
          <Box sx={{ color: "text.secondary" }}>This user has no posts yet.</Box>
        )}
      </Box>
    </Container>
  );
}

function ContactRow({ icon, label, value }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Box sx={{ color: "text.secondary", display: "flex" }}>{icon}</Box>
      <Box>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="body2">{value}</Typography>
      </Box>
    </Box>
  );
}
