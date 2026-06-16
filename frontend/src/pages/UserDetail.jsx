// Detail page for one user (route: /users/:id).
//
// Three modes are mixed in here:
//   * Read-only profile + paginated post list (works for any user).
//   * Profile editor — visible only when `authUser.id === user.id`. Sends
//     PATCH /api/user/<id> and updates the AuthProvider cache so the TopBar
//     reflects a new name immediately.
//   * Change-password panel — same own-only gate, calls
//     POST /api/auth/change-password (which also kills all other sessions).
//
// All "edit" actions are double-gated: the UI hides them off-profile, and
// the server returns 404 if a forged request tries to edit a foreign user.

import { useCallback, useEffect, useRef, useState } from "react";
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
  TextField,
} from "@mui/material";
import EmailIcon from "@mui/icons-material/EmailOutlined";
import PhoneIcon from "@mui/icons-material/PhoneOutlined";
import LanguageIcon from "@mui/icons-material/Language";
import BusinessIcon from "@mui/icons-material/BusinessOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import EditIcon from "@mui/icons-material/Edit";
import PersonAddIcon from "@mui/icons-material/PersonAddAlt1";
import PersonRemoveIcon from "@mui/icons-material/PersonRemoveAlt1";
import SinglePost from "../components/SinglePost";
import {
  fetchUser,
  fetchUserPosts,
  updateUser as apiUpdateUser,
  changePassword as apiChangePassword,
  followUser as apiFollowUser,
  unfollowUser as apiUnfollowUser,
} from "../api";
import { useAuth } from "../auth.jsx";

const PAGE_SIZE = 10;

export default function UserDetail() {
  const { id } = useParams();
  const { user: authUser, updateUser: cacheAuthUser } = useAuth();
  const [user, setUser] = useState(null);
  const [userLoading, setUserLoading] = useState(true);
  const [userError, setUserError] = useState(null);

  const [posts, setPosts] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [postsError, setPostsError] = useState(null);
  const [followBusy, setFollowBusy] = useState(false);

  const [editingProfile, setEditingProfile] = useState(false);
  const [profileDraft, setProfileDraft] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);

  const [pwdOpen, setPwdOpen] = useState(false);
  const [pwdCurrent, setPwdCurrent] = useState("");
  const [pwdNew, setPwdNew] = useState("");
  const [pwdError, setPwdError] = useState(null);
  const [pwdOk, setPwdOk] = useState(false);
  const [pwdBusy, setPwdBusy] = useState(false);

  // True only when the page is showing the signed-in user. Drives the
  // visibility of every "Edit" / "Change password" affordance on this page.
  const isOwnProfile = authUser && user && authUser.id === user.id;

  function openPwd() {
    setPwdCurrent("");
    setPwdNew("");
    setPwdError(null);
    setPwdOk(false);
    setPwdOpen(true);
  }

  function closePwd() {
    setPwdOpen(false);
    setPwdError(null);
  }

  // Submit a password change. The server returns 401 both when the session
  // is gone and when the supplied current password doesn't match — same
  // status code so we don't leak which case we hit.
  async function savePassword() {
    setPwdBusy(true);
    setPwdError(null);
    setPwdOk(false);
    try {
      await apiChangePassword({ current_password: pwdCurrent, new_password: pwdNew });
      setPwdOk(true);
      setPwdCurrent("");
      setPwdNew("");
    } catch (err) {
      if (err.status === 401) {
        setPwdError("Current password is incorrect (or your session expired).");
      } else if (err.status === 400) {
        setPwdError(err.message || "Invalid request");
      } else {
        setPwdError(err.message || "Failed to change password");
      }
    } finally {
      setPwdBusy(false);
    }
  }

  // Open the editor with the current profile values pre-filled. We keep a
  // separate draft object so Cancel doesn't mutate the displayed user.
  function startProfileEdit() {
    setProfileDraft({
      name: user.name || "",
      bio: user.bio || "",
      phone: user.phone || "",
      website: user.website || "",
      company: user.company || "",
      avatar_seed: user.avatar_seed || "",
    });
    setProfileError(null);
    setEditingProfile(true);
  }

  function cancelProfileEdit() {
    setEditingProfile(false);
    setProfileError(null);
  }

  // Persist the draft. On success we update two pieces of state:
  //   1. local `user` — the rest of the page re-renders with the new fields
  //   2. AuthProvider's cached user — so the TopBar (and anywhere else the
  //      cached `name` is shown) refreshes without a navigation.
  async function saveProfile() {
    setProfileSaving(true);
    setProfileError(null);
    try {
      const updated = await apiUpdateUser(user.id, profileDraft);
      setUser((prev) => ({ ...prev, ...updated }));
      cacheAuthUser({ id: updated.id, name: updated.name, email: updated.email });
      setEditingProfile(false);
    } catch (err) {
      if (err.status === 401) {
        setProfileError("Session expired. Please log in again.");
      } else if (err.status === 404) {
        setProfileError("You can only edit your own profile.");
      } else {
        setProfileError(err.message || "Failed to save");
      }
    } finally {
      setProfileSaving(false);
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUserLoading(true);
    setUserError(null);
    fetchUser(id)
      .then(setUser)
      .catch((err) => setUserError(err.message))
      .finally(() => setUserLoading(false));
  }, [id]);

  // Follow / unfollow the displayed user. The endpoint returns the fresh
  // counts + isFollowing, which we merge straight into the user state.
  async function toggleFollow() {
    if (!user) return;
    setFollowBusy(true);
    try {
      const res = user.isFollowing
        ? await apiUnfollowUser(user.id)
        : await apiFollowUser(user.id);
      setUser((prev) => ({ ...prev, ...res }));
    } catch {
      // Non-fatal — leave the button state unchanged on error.
    } finally {
      setFollowBusy(false);
    }
  }

  // The IntersectionObserver is created once and can't read fresh state, so the
  // values it needs (current user id, page, hasMore) live in refs.
  const pageRef = useRef(0);
  const idRef = useRef(id);
  const hasMoreRef = useRef(true);
  const inFlight = useRef(false);
  const observerRef = useRef(null);

  // Stable loader — takes the target user id so it never closes over a stale one.
  const fetchPage = useCallback(async (targetId, targetPage, reset) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setPostsLoading(true);
    setPostsError(null);
    try {
      const data = await fetchUserPosts(targetId, targetPage, PAGE_SIZE);
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
      setPostsError(err.message);
      hasMoreRef.current = false;
      setHasMore(false);
    } finally {
      setPostsLoading(false);
      inFlight.current = false;
    }
  }, []);

  // Reset and load page 1 whenever we switch to a different user. fetchPage
  // (called below) re-sets hasMore from the response; we only reset the refs.
  useEffect(() => {
    idRef.current = id;
    pageRef.current = 0;
    hasMoreRef.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchPage(id, 1, true);
  }, [id, fetchPage]);

  // Callback ref on the sentinel: wires up infinite scroll when it mounts.
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
            fetchPage(idRef.current, pageRef.current + 1, false);
          }
        },
        { rootMargin: "300px" }
      );
      observer.observe(node);
      observerRef.current = observer;
    },
    [fetchPage]
  );

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
            <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1.5, flexWrap: "wrap" }}>
              <Chip label={`${user.postCount ?? posts.length} posts`} size="small" color="primary" />
              <Chip label={`${user.followersCount ?? 0} followers`} size="small" variant="outlined" />
              <Chip label={`${user.followingCount ?? 0} following`} size="small" variant="outlined" />
            </Stack>
          </Box>
          {isOwnProfile && !editingProfile && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EditIcon fontSize="small" />}
              onClick={startProfileEdit}
              sx={{ alignSelf: { xs: "flex-start", sm: "flex-start" }, textTransform: "none" }}
            >
              Edit profile
            </Button>
          )}
          {authUser && !isOwnProfile && (
            <Button
              variant={user.isFollowing ? "outlined" : "contained"}
              size="small"
              startIcon={user.isFollowing ? <PersonRemoveIcon fontSize="small" /> : <PersonAddIcon fontSize="small" />}
              onClick={toggleFollow}
              disabled={followBusy}
              sx={{ alignSelf: "flex-start", textTransform: "none", fontWeight: 600 }}
            >
              {user.isFollowing ? "Unfollow" : "Follow"}
            </Button>
          )}
        </Box>

        <Divider sx={{ my: 2 }} />

        {editingProfile ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Name"
              value={profileDraft.name}
              onChange={(e) => setProfileDraft((d) => ({ ...d, name: e.target.value }))}
              size="small"
              required
            />
            <TextField
              label="Bio"
              value={profileDraft.bio}
              onChange={(e) => setProfileDraft((d) => ({ ...d, bio: e.target.value }))}
              size="small"
              multiline
              minRows={2}
            />
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Phone"
                  value={profileDraft.phone}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, phone: e.target.value }))}
                  size="small"
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Website"
                  value={profileDraft.website}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, website: e.target.value }))}
                  size="small"
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Company"
                  value={profileDraft.company}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, company: e.target.value }))}
                  size="small"
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label="Avatar seed"
                  value={profileDraft.avatar_seed}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, avatar_seed: e.target.value }))}
                  size="small"
                  fullWidth
                  helperText="DiceBear seed — pick any string"
                />
              </Grid>
            </Grid>
            {profileError && <Alert severity="error">{profileError}</Alert>}
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                onClick={saveProfile}
                disabled={profileSaving || !profileDraft.name.trim()}
                sx={{ textTransform: "none" }}
              >
                {profileSaving ? "Saving..." : "Save"}
              </Button>
              <Button
                variant="outlined"
                onClick={cancelProfileEdit}
                disabled={profileSaving}
                sx={{ textTransform: "none" }}
              >
                Cancel
              </Button>
            </Stack>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {user.email && (
              <Grid size={{ xs: 12, sm: 6 }}>
                <ContactRow icon={<EmailIcon fontSize="small" />} label="Email" value={user.email} />
              </Grid>
            )}
            {user.phone && (
              <Grid size={{ xs: 12, sm: 6 }}>
                <ContactRow icon={<PhoneIcon fontSize="small" />} label="Phone" value={user.phone} />
              </Grid>
            )}
            {user.website && (
              <Grid size={{ xs: 12, sm: 6 }}>
                <ContactRow icon={<LanguageIcon fontSize="small" />} label="Website" value={user.website} />
              </Grid>
            )}
            {user.company && (
              <Grid size={{ xs: 12, sm: 6 }}>
                <ContactRow icon={<BusinessIcon fontSize="small" />} label="Company" value={user.company} />
              </Grid>
            )}
          </Grid>
        )}
      </Paper>

      {isOwnProfile && (
        <Paper elevation={1} sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Typography variant="h6" fontWeight={700}>
              Password
            </Typography>
            {!pwdOpen ? (
              <Button variant="outlined" size="small" onClick={openPwd} sx={{ textTransform: "none" }}>
                Change password
              </Button>
            ) : (
              <Button variant="text" size="small" onClick={closePwd} sx={{ textTransform: "none" }}>
                Close
              </Button>
            )}
          </Box>
          {pwdOpen && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
              <TextField
                label="Current password"
                type="password"
                autoComplete="current-password"
                value={pwdCurrent}
                onChange={(e) => setPwdCurrent(e.target.value)}
                size="small"
                required
              />
              <TextField
                label="New password"
                type="password"
                autoComplete="new-password"
                value={pwdNew}
                onChange={(e) => setPwdNew(e.target.value)}
                size="small"
                helperText="At least 8 characters"
                required
              />
              {pwdError && <Alert severity="error">{pwdError}</Alert>}
              {pwdOk && <Alert severity="success">Password changed. Other sessions were signed out.</Alert>}
              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  onClick={savePassword}
                  disabled={pwdBusy || !pwdCurrent || pwdNew.length < 8}
                  sx={{ textTransform: "none" }}
                >
                  {pwdBusy ? "Saving..." : "Save"}
                </Button>
              </Stack>
            </Box>
          )}
        </Paper>
      )}

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
        {postsLoading ? (
          <CircularProgress />
        ) : !hasMore && posts.length > 0 ? (
          <Box sx={{ color: "text.secondary" }}>No more posts.</Box>
        ) : !hasMore && posts.length === 0 ? (
          <Box sx={{ color: "text.secondary" }}>This user has no posts yet.</Box>
        ) : null}
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
