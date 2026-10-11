import { redirect } from "next/navigation";

// The dashboard is the app's home page.
export default function Home() {
  redirect("/dashboard");
}
