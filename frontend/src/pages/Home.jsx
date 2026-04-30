import { Container, Typography, Box } from "@mui/material";
import Feed from "../components/Feed";

export default function Home() {
  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight={700}>
          Feed
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Posts from all users
        </Typography>
      </Box>
      <Feed />
    </Container>
  );
}
