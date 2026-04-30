import { useEffect, useRef, useState } from "react";
import {
  Grid,
  Button,
  Box,
  CircularProgress,
  Alert,
} from "@mui/material";
import SinglePost from "./SinglePost";
import { fetchPosts } from "../api";

const PAGE_SIZE = 10;

export default function Feed() {
  const [posts, setPosts] = useState([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const inFlight = useRef(false);

  async function loadNext() {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    try {
      const nextPage = page + 1;
      const data = await fetchPosts(nextPage, PAGE_SIZE);
      setPosts((prev) => {
        const seen = new Set(prev.map((p) => p.id));
        const fresh = data.items.filter((p) => !seen.has(p.id));
        return [...prev, ...fresh];
      });
      setPage(nextPage);
      setHasMore(data.has_more);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      inFlight.current = false;
    }
  }

  useEffect(() => {
    loadNext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {posts.map((post) => (
          <Grid size={{ xs: 12, md: 6 }} key={post.id}>
            <SinglePost post={post} />
          </Grid>
        ))}
      </Grid>

      <Box sx={{ display: "flex", justifyContent: "center", mt: 3, mb: 2 }}>
        {loading ? (
          <CircularProgress />
        ) : hasMore ? (
          <Button variant="contained" size="large" onClick={loadNext}>
            Load More
          </Button>
        ) : posts.length > 0 ? (
          <Box sx={{ color: "text.secondary" }}>No more posts.</Box>
        ) : null}
      </Box>
    </Box>
  );
}
