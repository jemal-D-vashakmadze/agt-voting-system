import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import Home from "./page";

beforeEach(() => {
  global.fetch = jest.fn() as jest.Mock;
});

afterEach(() => {
  jest.restoreAllMocks();
});

test("renders title, contestant list, and form controls", () => {
  render(<Home />);
  expect(screen.getByText("AGT Voting System")).toBeInTheDocument();
  expect(screen.getByText(/Valid contestants:.*Chen/)).toBeInTheDocument();
  expect(screen.getByLabelText("Contestant Last Name")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vote" })).toBeInTheDocument();
});

test("successful vote shows green alert and disables form", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => ({ message: "Vote recorded for Thompson." }),
  });

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("Vote recorded for Thompson.");
  expect(alert.className).toContain("Success");

  expect(screen.getByLabelText("Contestant Last Name")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Vote" })).toBeDisabled();
});

test("404 error shows red alert", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    json: async () => ({
      detail: "Unknown contestant: 'yamamoto'. Valid contestants: Chen, Jensen, Kowalski, Martinez, Nakamura, Okafor, Patel, Rodriguez, Thompson, Williams.",
    }),
  });

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "yamamoto");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent(/Unknown contestant/);
  expect(alert.className).toContain("Error");
});

test("409 error shows red alert", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    json: async () => ({ detail: "You have already voted." }),
  });

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("You have already voted.");
  expect(alert.className).toContain("Error");
});

test("429 error shows red alert", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    json: async () => ({ detail: "Rate limit exceeded. Try again later." }),
  });

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("Rate limit exceeded. Try again later.");
  expect(alert.className).toContain("Error");
});

test("network error shows red alert", async () => {
  (global.fetch as jest.Mock).mockRejectedValueOnce(
    new TypeError("Failed to fetch")
  );

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  const alert = screen.getByRole("alert");
  expect(alert).toHaveTextContent("Network error. Please try again.");
  expect(alert.className).toContain("Error");
});

test("input preserved on error, cleared on success", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    json: async () => ({ detail: "Unknown contestant." }),
  });

  const { unmount } = render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "yamamoto");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  expect(screen.getByLabelText("Contestant Last Name")).toHaveValue("yamamoto");
  unmount();

  // Success: input cleared
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => ({ message: "Vote recorded for Thompson." }),
  });

  render(<Home />);
  const user2 = userEvent.setup();

  await user2.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user2.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(screen.getByText("Vote recorded for Thompson.")).toBeInTheDocument();
  });

  expect(screen.getByLabelText("Contestant Last Name")).toHaveValue("");
});

test("correct API request sent", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => ({ message: "Vote recorded for Thompson." }),
  });

  render(<Home />);
  const user = userEvent.setup();

  await user.type(screen.getByLabelText("Contestant Last Name"), "Thompson");
  await user.click(screen.getByRole("button", { name: "Vote" }));

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/vote",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contestant: "Thompson" }),
      }
    );
  });
});
