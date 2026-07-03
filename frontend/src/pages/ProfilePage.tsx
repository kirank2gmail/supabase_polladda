import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { changePassword, getTimezones, updateNickname, updateTimezone } from "../api/auth";

export function ProfilePage() {
  const { user, refreshUser } = useAuth();

  return (
    <div className="mx-auto max-w-xl p-4">
      <h1 className="mb-4 text-xl font-bold">👤 My Profile</h1>
      {user && (
        <div className="space-y-4">
          <NicknameCard nickname={user.nickname} onSaved={refreshUser} />
          <PasswordCard />
          <TimezoneCard currentTz={user.timezone} onSaved={refreshUser} />
        </div>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-gray-200 p-4">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {children}
    </div>
  );
}

function NicknameCard({
  nickname,
  onSaved,
}: {
  nickname: string;
  onSaved: () => Promise<void>;
}) {
  const [value, setValue] = useState(nickname);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const save = async () => {
    if (!value.trim()) {
      setMessage({ text: "Nickname cannot be empty.", ok: false });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await updateNickname(value.trim());
      await onSaved();
      setMessage({ text: "Nickname saved!", ok: true });
    } catch (e) {
      setMessage({ text: String(e), ok: false });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Nickname">
      <p className="mb-2 text-xs text-gray-500">
        Shown on leaderboard and results. Current: <b>{nickname}</b>
      </p>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button
          disabled={saving}
          onClick={save}
          className="rounded bg-[#28324f] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Save
        </button>
      </div>
      {message && (
        <p className={`mt-2 text-sm ${message.ok ? "text-green-700" : "text-red-600"}`}>
          {message.text}
        </p>
      )}
    </Card>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [n1, setN1] = useState("");
  const [n2, setN2] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const save = async () => {
    setMessage(null);
    if (n1.length < 6) {
      setMessage({ text: "Min 6 characters required.", ok: false });
      return;
    }
    if (n1 !== n2) {
      setMessage({ text: "Passwords do not match.", ok: false });
      return;
    }
    setSaving(true);
    try {
      await changePassword(n1, current);
      setMessage({ text: "Password updated!", ok: true });
      setCurrent("");
      setN1("");
      setN2("");
    } catch (e) {
      setMessage({ text: String(e), ok: false });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Change Password">
      <div className="space-y-2">
        <input
          type="password"
          placeholder="Current password"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <input
          type="password"
          placeholder="New password (min 6)"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          value={n1}
          onChange={(e) => setN1(e.target.value)}
        />
        <input
          type="password"
          placeholder="Confirm new password"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          value={n2}
          onChange={(e) => setN2(e.target.value)}
        />
        <button
          disabled={saving}
          onClick={save}
          className="rounded bg-[#28324f] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Update Password
        </button>
      </div>
      {message && (
        <p className={`mt-2 text-sm ${message.ok ? "text-green-700" : "text-red-600"}`}>
          {message.text}
        </p>
      )}
    </Card>
  );
}

function TimezoneCard({
  currentTz,
  onSaved,
}: {
  currentTz: string;
  onSaved: () => Promise<void>;
}) {
  const [zones, setZones] = useState<string[]>([currentTz]);
  const [value, setValue] = useState(currentTz);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  useEffect(() => {
    getTimezones()
      .then((z) => {
        const merged = [...z.common, ...z.all.filter((t) => !z.common.includes(t))];
        setZones(merged);
      })
      .catch(() => {
        /* keep fallback single-item list */
      });
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await updateTimezone(value);
      await onSaved();
      setMessage({ text: `Timezone set to ${value}`, ok: true });
    } catch (e) {
      setMessage({ text: String(e), ok: false });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Timezone">
      <div className="flex gap-2">
        <select
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        >
          {zones.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
        <button
          disabled={saving}
          onClick={save}
          className="rounded bg-[#28324f] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Save
        </button>
      </div>
      {message && (
        <p className={`mt-2 text-sm ${message.ok ? "text-green-700" : "text-red-600"}`}>
          {message.text}
        </p>
      )}
    </Card>
  );
}
