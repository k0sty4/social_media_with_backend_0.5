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
  TextField,
} from "@mui/material";
import EmailIcon from "@mui/icons-material/EmailOutlined";
import PhoneIcon from "@mui/icons-material/PhoneOutlined";
import LanguageIcon from "@mui/icons-material/Language";
import BusinessIcon from "@mui/icons-material/BusinessOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import EditIcon from "@mui/icons-material/Edit";
import SinglePost from "../components/SinglePost";
import {
  fetchUser,
  fetchUserPosts,
  updateUser as apiUpdateUser,
  changePassword as apiChangePassword,
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
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [postsError, setPostsError] = useState(null);

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

  async function saveProfile() {
    setProfileSaving(true);
    setProfileError(null);
    try {
      const updated = await apiUpdateUser(user.id, profileDraft);
      setUser((prev) => ({ ...prev, ...updated }));
      // keep the AuthProvider's cached user in sync so the TopBar reflects the new name
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
