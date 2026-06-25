import { useEffect, useMemo, useState } from "react";
import ModuleShell from "@/components/v3.11/ModuleShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/context/ToastContext";

const API_BASE = "/api";

type Role = "owner" | "admin" | "bookkeeper" | "viewer";
type Profile = { id: number; name: string };
type Member = {
  id: number;
  user_id: number;
  profile_id: number;
  role: Role;
  created_at: string;
};
type User = { id: number; username: string };

const ROLES: Role[] = ["owner", "admin", "bookkeeper", "viewer"];

export default function RoleManager() {
  const { addToast } = useToast();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [members, setMembers] = useState<Member[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [newUserId, setNewUserId] = useState<string>("");
  const [newRole, setNewRole] = useState<Role>("viewer");

  useEffect(() => {
    fetch(`${API_BASE}/profiles`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Failed to load profiles"))))
      .then((data: Profile[]) => {
        setProfiles(data);
        if (data.length && !selectedProfileId) {
          setSelectedProfileId(String(data[0].id));
        }
      })
      .catch((err) => addToast(err.message, "error"));
  }, []);

  useEffect(() => {
    if (!selectedProfileId) return;
    fetch(`${API_BASE}/profiles/${selectedProfileId}/members`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Failed to load members"))))
      .then((data: Member[]) => setMembers(data))
      .catch((err) => addToast(err.message, "error"));
  }, [selectedProfileId]);

  // Minimal user discovery: reuse the /auth/me endpoint plus a small local cache.
  useEffect(() => {
    fetch(`${API_BASE}/auth/me`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Auth required"))))
      .then((me: User) => {
        if (!users.find((u) => u.id === me.id)) {
          setUsers((prev) => [...prev, me]);
        }
      })
      .catch((err) => addToast(err.message, "error"));
  }, []);

  const selectedProfileName = useMemo(
    () => profiles.find((p) => String(p.id) === selectedProfileId)?.name ?? "",
    [profiles, selectedProfileId]
  );

  const handleAddMember = async () => {
    const userId = parseInt(newUserId, 10);
    if (!userId || !selectedProfileId) return;
    const res = await fetch(`${API_BASE}/profiles/${selectedProfileId}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, role: newRole }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: "Add failed" }));
      addToast(detail.detail, "error");
      return;
    }
    const added: Member = await res.json();
    setMembers((prev) => {
      const filtered = prev.filter((m) => m.user_id !== added.user_id);
      return [...filtered, added];
    });
    setNewUserId("");
    addToast("Member added", "success");
  };

  const handleChangeRole = async (userId: number, role: Role) => {
    const res = await fetch(`${API_BASE}/profiles/${selectedProfileId}/members/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: "Update failed" }));
      addToast(detail.detail, "error");
      return;
    }
    const updated: Member = await res.json();
    setMembers((prev) => prev.map((m) => (m.user_id === updated.user_id ? updated : m)));
    addToast("Role updated", "success");
  };

  const handleRemove = async (userId: number) => {
    const res = await fetch(`${API_BASE}/profiles/${selectedProfileId}/members/${userId}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: "Remove failed" }));
      addToast(detail.detail, "error");
      return;
    }
    setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    addToast("Member removed", "success");
  };

  return (
    <ModuleShell
      title="Profile Roles & Memberships"
      description="Manage who can access each profile and what they can do."
      moduleId="3.11.02"
    >
      <div className="space-y-6">
        <div className="flex items-end gap-4">
          <div className="flex-1 space-y-2">
            <label className="text-sm font-medium text-text-secondary">Profile</label>
            <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
              <SelectTrigger className="bg-canvas border-divider">
                <SelectValue placeholder="Select a profile" />
              </SelectTrigger>
              <SelectContent className="bg-canvas border-divider">
                {profiles.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {selectedProfileId && (
          <Card className="bg-canvas border-divider">
            <CardHeader>
              <CardTitle className="text-text-primary text-lg">
                Members of {selectedProfileName}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {members.length === 0 && (
                <p className="text-text-secondary text-sm">
                  No explicit members. The profile owner has full access automatically.
                </p>
              )}
              {members.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between rounded-md border border-divider p-3"
                >
                  <div className="space-y-1">
                    <div className="text-text-primary font-medium">
                      User #{member.user_id}
                    </div>
                    <Badge variant="outline" className="border-gold/30 text-gold">
                      {member.role}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select
                      value={member.role}
                      onValueChange={(value) => handleChangeRole(member.user_id, value as Role)}
                    >
                      <SelectTrigger className="bg-canvas border-divider w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-canvas border-divider">
                        {ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleRemove(member.user_id)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              ))}

              <Separator className="bg-divider" />

              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1 space-y-2">
                  <label className="text-sm font-medium text-text-secondary">User ID</label>
                  <Input
                    type="number"
                    value={newUserId}
                    onChange={(e) => setNewUserId(e.target.value)}
                    placeholder="Enter existing user id"
                    className="bg-canvas border-divider"
                  />
                </div>
                <div className="w-full sm:w-40 space-y-2">
                  <label className="text-sm font-medium text-text-secondary">Role</label>
                  <Select value={newRole} onValueChange={(value) => setNewRole(value as Role)}>
                    <SelectTrigger className="bg-canvas border-divider">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-canvas border-divider">
                      {ROLES.map((r) => (
                        <SelectItem key={r} value={r}>
                          {r}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={handleAddMember} className="bg-gold text-canvas hover:bg-gold/90">
                  Add Member
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ModuleShell>
  );
}
