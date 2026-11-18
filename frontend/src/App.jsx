import { Link, Navigate, Route, Routes } from "react-router";
import { homePathFor, useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { PageLoader } from "./components/States";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ComplaintDetail from "./pages/citizen/ComplaintDetail";
import Location from "./pages/citizen/Location";
import MyComplaints from "./pages/citizen/MyComplaints";
import Nearby from "./pages/citizen/Nearby";
import NewComplaint from "./pages/citizen/NewComplaint";
import Submitted from "./pages/citizen/Submitted";
import Queue from "./pages/officer/Queue";
import TicketDetail from "./pages/officer/TicketDetail";
import Triage from "./pages/admin/Triage";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  return <Navigate to={homePathFor(user)} replace />;
}

function NotFound() {
  return (
    <div className="card py-12 text-center">
      <p className="text-lg font-semibold">Page not found</p>
      <Link to="/" className="btn btn-primary mt-4">
        Go home
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<ProtectedRoute roles={["citizen"]} />}>
          <Route path="/location" element={<Location />} />
          <Route path="/nearby" element={<Nearby />} />
          <Route path="/complaints" element={<MyComplaints />} />
          <Route path="/complaints/new" element={<NewComplaint />} />
          <Route path="/complaints/:ticketNo/submitted" element={<Submitted />} />
        </Route>

        {/* Linked from emails, so any logged-in role may open it */}
        <Route element={<ProtectedRoute />}>
          <Route path="/complaints/:ticketNo" element={<ComplaintDetail />} />
        </Route>

        <Route element={<ProtectedRoute roles={["officer"]} />}>
          <Route path="/officer" element={<Queue />} />
          <Route path="/officer/tickets/:ticketNo" element={<TicketDetail />} />
        </Route>

        <Route element={<ProtectedRoute roles={["admin"]} />}>
          <Route path="/admin/triage" element={<Triage />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
