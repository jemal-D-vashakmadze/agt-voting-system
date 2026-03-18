"use client";

import { useState, FormEvent } from "react";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CONTESTANTS =
  "Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams";

export default function Home() {
  const [contestant, setContestant] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<"success" | "error">("success");
  const [voted, setVoted] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      const res = await fetch(`${API_URL}/api/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contestant }),
      });

      const data = await res.json();

      if (res.ok) {
        setMessage(data.message);
        setSeverity("success");
        setVoted(true);
        setContestant("");
      } else {
        setMessage(data.detail || "An error occurred.");
        setSeverity("error");
      }
    } catch {
      setMessage("Network error. Please try again.");
      setSeverity("error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <main className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">
          AGT Voting System
        </h1>

        <p className="text-sm text-gray-600 mb-4">
          Valid contestants: {CONTESTANTS}
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <TextField
            label="Contestant Last Name"
            value={contestant}
            onChange={(e) => setContestant(e.target.value)}
            disabled={loading || voted}
            fullWidth
          />

          <Button
            type="submit"
            variant="contained"
            disabled={loading || voted}
          >
            {loading ? "Voting..." : "Vote"}
          </Button>
        </form>

        {message && (
          <Alert severity={severity} className="mt-4">
            {message}
          </Alert>
        )}
      </main>
    </div>
  );
}
