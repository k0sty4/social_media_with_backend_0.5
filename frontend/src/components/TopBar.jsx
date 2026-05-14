import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const PUBLIC_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/users", label: "Users" },
  { to: "/about", label: "About" },
];

const linkSx = {
  color: "white",
  "&.active": { fontWeight: 700, textDecoration: "underline" },
};

export default function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography
          variant="h6"
          component={NavLink}
          to="/"
          sx={{
            flexGrow: 1,
            color: "inherit",
            textDecoration: "none",
            fontWeight: 700,
          }}
        >
          MyApp
        </Typography>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          {PUBLIC_LINKS.map((link) => (
            <Button
              key={link.to}
              component={NavLink}
              to={link.to}
              end={link.end}
              sx={linkSx}
            >
              {link.label}
            </Button>
          ))}
          {user ? (
            <>
              <Typography sx={{ color: "white", mx: 1 }}>
                {user.name || user.email}
              </Typography>
              <Button onClick={handleLogout} sx={{ color: "white" }}>
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button component={NavLink} to="/login" sx={linkSx}>
                Login
              </Button>
              <Button component={NavLink} to="/register" sx={linkSx}>
                Register
              </Button>
            </>
          )}
        </Box>
      </Toolbar>
    </AppBar>
  );
}
