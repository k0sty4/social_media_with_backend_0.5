import { useCallback, useEffect, useRef, useState } from "react";
import {
  Grid,
  Button,
  Box,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Stack,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SinglePost from "./SinglePost";
import CreatePostDialog from "./CreatePostDialog";
import { fetchPosts } from "../api";
import { useAuth } from "../auth.jsx";

const PAGE_SIZE = 10;

export default function Feed() {
  const { user } = useAuth();
  // "all" = global feed, "following" = posts by people the user follows.
  const [scope, setScope] = useState("all");
  const [posts, setPosts] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [composeOpen, setComposeOpen] = useState(false);

  // The IntersectionObserver callback can't read fresh state (it's created
  // once), so the values it needs live in refs that we keep up to date.
  const pageRef = useRef(0);
  const scopeRef = useRef(scope);
  const hasMoreRef = useRef(true);
  const inFlight = useRef(false);
  const observerRef = useRef(null);

  // Stable loader (no deps) — everything it needs is passed in or read from a
  // ref, so it never goes stale and the observer below can depend on it safely.
  const fetchPage = useCallback(async (targetScope, targetPage, reset) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPosts(targetPage, PAGE_SIZE, targetScope);
      setPosts((prev) => {
        const base = reset ? [] : prev;
        const seen = new Set(base.map((p) => p.id));
        const fresh = data.items.filter((p) => !seen.has(p.id));
        return [...base, ...fresh];
      });
      pageRef.current = targetPage;
      hasMoreRef.current = data.has_more;
      setHasMore(data.has_more);
    } catch (err) {
      setError(err.message);
      hasMoreRef.current = false;
      setHasMore(false);
    } finally {
      setLoading(false);
      inFlight.current = false;
    }
  }, []);

  // Initial load of the global feed (runs once). Fetching on mount is the
  // intended use of an effect; fetchPage owns its own setState.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchPage("all", 1, true);
  }, [fetchPage]);

  // Switching tabs resets pagination and reloads from page 1 for the new scope.
  function changeScope(next) {
    if (next === scope) return;
    setScope(next);
    scopeRef.current = next;
    pageRef.current = 0;
    hasMoreRef.current = true;
    setHasMore(true);
    fetchPage(next, 1, true);
  }

  // Callback ref on the sentinel: (re)wires the IntersectionObserver when the
  // node mounts. When the sentinel scrolls into view we pull the next page.
  const sentinelRef = useCallback(
    (node) => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      if (!node) return;
      const observer = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && !inFlight.current && hasMoreRef.current) {
            fetchPage(scopeRef.current, pageRef.current + 1, false);
          }
        },
        { rootMargin: "300px" }
      );
      observer.observe(node);
      observerRef.current = observer;
    },
    [fetchPage]
  );

  function handleCreated(post) {
    // Prepend the new post so the author sees it immediately.
    setPosts((prev) => [post, ...prev.filter((p) => p.id !== post.id)]);
  }

  // If the user is signed out, never present the (auth-only) Following tab.
  const tabValue = user ? scope : "all";

  return (
    <Box>
      <Stack
        direction="row"
        sx={{ mb: 2, flexWrap: "wrap", gap: 1, justifyContent: "space-between", alignItems: "center" }}
      >
        <Tabs value={tabValue} onChange={(_, v) => changeScope(v)}>
          <Tab value="all" label="Global" sx={{ textTransform: "none" }} />
          {user && <Tab value="following" label="Following" sx={{ textTransform: "none" }} />}
        </Tabs>
        {user && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setComposeOpen(true)}
            sx={{ textTransform: "none", fontWeight: 600 }}
          >
            New Post
          </Button>
        )}
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {posts.map((post) => (
          <Grid size={{ xs: 12, md: 6 }} key={post.id}>
            <SinglePost
              post={post}
              onPostUpdated={(updated) =>
                setPosts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
              }
            />
          </Grid>
        ))}
      </Grid>

      {/* Sentinel watched by the IntersectionObserver to drive infinite scroll. */}
      <Box
        ref={sentinelRef}
        sx={{ display: "flex", justifyContent: "center", mt: 3, mb: 2, minHeight: 48 }}
      >
        {loading ? (
          <CircularProgress />
        ) : !hasMore && posts.length > 0 ? (
          <Box sx={{ color: "text.secondary" }}>No more posts.</Box>
        ) : !hasMore && posts.length === 0 ? (
          <Box sx={{ color: "text.secondary" }}>
            {scope === "following"
              ? "No posts yet — follow some users to fill this feed."
              : "No posts yet."}
          </Box>
        ) : null}
      </Box>

      <CreatePostDialog
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        onCreated={handleCreated}
      />
    </Box>
  );
}
