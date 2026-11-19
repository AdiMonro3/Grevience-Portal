import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import Modal from "../../components/Modal";
import { EmptyState, ErrorBox, Notice, PageLoader, Spinner } from "../../components/States";

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function randomPassword() {
  const words = ["Neem", "Peepal", "Ashoka", "Banyan", "Gulmohar", "Mango"];
  const word = words[Math.floor(Math.random() * words.length)];
  return `${word}@${Math.floor(1000 + Math.random() * 9000)}`;
}

function AddOfficerDialog({ departments, wards, defaults, onClose, onDone }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    password: randomPassword(),
    department_id: defaults.department_id,
    ward_id: defaults.ward_id,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/admin/officers", {
        ...form,
        phone: form.phone.trim() || null,
        department_id: Number(form.department_id),
        ward_id: Number(form.ward_id),
      });
      onDone(data, `${data.name} added. They can log in with ${data.email} and the password ${form.password}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Add officer" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label" htmlFor="o-name">Full name</label>
            <input id="o-name" className="input" value={form.name} onChange={set("name")} required minLength={2} maxLength={120} />
          </div>
          <div>
            <label className="label" htmlFor="o-email">Email</label>
            <input id="o-email" type="email" className="input" value={form.email} onChange={set("email")} required />
          </div>
          <div>
            <label className="label" htmlFor="o-phone">Phone (optional)</label>
            <input id="o-phone" type="tel" className="input" value={form.phone} onChange={set("phone")} maxLength={20} />
          </div>
          <div>
            <label className="label" htmlFor="o-dept">Department</label>
            <select id="o-dept" className="input" value={form.department_id} onChange={set("department_id")} required>
              <option value="">Choose…</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="o-ward">Ward</label>
            <select id="o-ward" className="input" value={form.ward_id} onChange={set("ward_id")} required>
              <option value="">Choose…</option>
              {wards.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="o-password">Initial password</label>
            <div className="flex gap-2">
              <input id="o-password" className="input font-mono" value={form.password} onChange={set("password")} required minLength={6} maxLength={72} />
              <button type="button" className="btn btn-secondary" onClick={() => setForm({ ...form, password: randomPassword() })}>
                New
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">Share it with the officer. They log in with their email and this password.</p>
          </div>
        </div>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Add officer
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DeactivateDialog({ officer, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      const { data } = await api.patch(`/admin/officers/${officer.id}`, { is_active: false });
      const returned = officer.open_tickets ? ` ${plural(officer.open_tickets, "ticket")} went back to the ward queue.` : "";
      onDone(data, `${officer.name} was deactivated.${returned}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Deactivate officer?" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-slate-700">
          <b>{officer.name}</b> will be logged out straight away and won't be able to log in.
          {officer.open_tickets > 0 && (
            <>
              {" "}Their {plural(officer.open_tickets, "picked-up ticket")} will go back to the{" "}
              {officer.department.name} queue for {officer.ward.name}.
            </>
          )}
        </p>
        <p className="text-xs text-slate-500">You can activate them again later.</p>
        <ErrorBox message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={confirm} disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} Deactivate
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function Officers() {
  const [officers, setOfficers] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [wards, setWards] = useState([]);
  const [wardFilter, setWardFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [highlight, setHighlight] = useState(null);
  const [dialog, setDialog] = useState(null); // { type: "add" } | { type: "deactivate", officer }
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const [o, d, w] = await Promise.all([api.get("/admin/officers"), api.get("/departments"), api.get("/wards")]);
      setOfficers(o.data);
      setDepartments(d.data);
      setWards(w.data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function upsert(updated, msg) {
    setOfficers((list) => {
      const exists = list.some((o) => o.id === updated.id);
      return exists ? list.map((o) => (o.id === updated.id ? updated : o)) : [updated, ...list];
    });
    setDialog(null);
    setMessage(msg);
    setHighlight(updated.id);
  }

  function added(officer, msg) {
    upsert(officer, msg);
    // make sure the new row is visible
    setWardFilter(String(officer.ward.id));
    setDeptFilter("");
  }

  async function activate(officer) {
    setBusyId(officer.id);
    setMessage("");
    try {
      const { data } = await api.patch(`/admin/officers/${officer.id}`, { is_active: true });
      upsert(data, `${officer.name} can log in again.`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  const shown =
    officers?.filter(
      (o) => (!wardFilter || String(o.ward.id) === wardFilter) && (!deptFilter || String(o.department.id) === deptFilter),
    ) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Officers</h1>
          <p className="text-sm text-slate-500">Each officer handles one department in one ward.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog({ type: "add" })} disabled={!officers}>
          + Add officer
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select className="input w-full sm:w-auto" value={wardFilter} onChange={(e) => setWardFilter(e.target.value)} aria-label="Filter by ward">
          <option value="">All wards</option>
          {wards.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
        <select className="input w-full sm:w-auto" value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)} aria-label="Filter by department">
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        {officers && (
          <span className="text-sm text-slate-500">
            {shown.length} of {plural(officers.length, "officer")}
          </span>
        )}
      </div>

      {message && <Notice tone="success">{message}</Notice>}
      <ErrorBox message={error} onRetry={load} />
      {officers === null && !error && <PageLoader />}
      {officers && shown.length === 0 && <EmptyState title="No officers match these filters" />}

      {shown.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-slate-50 text-xs tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3">Officer</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Ward</th>
                <th className="px-4 py-3" title="Picked up and not yet resolved">Open tickets</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((o) => (
                <tr key={o.id} className={`${o.is_active ? "" : "bg-slate-50 text-slate-500"} ${highlight === o.id ? "bg-green-50" : ""}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium">{o.name}</div>
                    <div className="text-xs text-slate-500">
                      {o.email}
                      {o.phone && ` · ${o.phone}`}
                    </div>
                  </td>
                  <td className="px-4 py-3">{o.department.name}</td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs font-semibold">{o.ward.code}</span>{" "}
                    <span className="text-slate-600">{o.ward.name.replace(/^Ward \d+ - /, "")}</span>
                  </td>
                  <td className="px-4 py-3">{o.open_tickets}</td>
                  <td className="px-4 py-3">
                    {o.is_active ? (
                      <span className="badge bg-green-100 text-green-800">Active</span>
                    ) : (
                      <span className="badge bg-slate-200 text-slate-700">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {o.is_active ? (
                      <button className="btn btn-secondary btn-sm text-red-700" onClick={() => setDialog({ type: "deactivate", officer: o })}>
                        Deactivate
                      </button>
                    ) : (
                      <button className="btn btn-secondary btn-sm" onClick={() => activate(o)} disabled={busyId === o.id}>
                        {busyId === o.id && <Spinner className="h-3 w-3" />} Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {dialog?.type === "add" && (
        <AddOfficerDialog
          departments={departments}
          wards={wards}
          defaults={{ department_id: deptFilter, ward_id: wardFilter }}
          onClose={() => setDialog(null)}
          onDone={added}
        />
      )}
      {dialog?.type === "deactivate" && (
        <DeactivateDialog officer={dialog.officer} onClose={() => setDialog(null)} onDone={upsert} />
      )}
    </div>
  );
}
