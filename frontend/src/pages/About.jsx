import { Container, Typography, Box } from "@mui/material";

export default function About() {
  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        About
      </Typography>
      <Box sx={{ mt: 2 }}>
        <Typography variant="body1" paragraph>
          MyApp is a small demo built on top of the Profile Explorer Flask API.
        </Typography>
        <Typography variant="body1" paragraph>
          Every time the backend starts, it pulls 10 new profiles from
          JSONPlaceholder and stores them locally in SQLite, each with a
          handful of generated posts. The React frontend reads those posts
          and profiles through a small JSON API.
        </Typography>
        <Typography variant="body1">
          Built with React, Vite, Material UI and Flask.
        </Typography>
      </Box>
    </Container>
  );
}
