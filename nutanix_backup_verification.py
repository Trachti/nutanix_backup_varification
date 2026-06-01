import argparse, http.client, json, ssl
from datetime import datetime, timedelta, timezone

NTNX_PRISMCENTRAL_IP = "YOUR_IP:9440"
PE_AND_PC_TOKEN = "YOUR GENERATED TOKEN FROM nutanix_auth.py"
PE_HOSTS_BY_CLUSTER_UUID = {
    "UUID_FROM_CLUSTER_1": "IP_FROM_ELEMENTS_CLUSTER_1:9440",
    "UUID_FROM_CLUSTER_2": "IP_FROM_ELEMENTS_CLUSTER_2:9440",
    "UUID_FROM_CLUSTER_3": "IP_FROM_ELEMENTS_CLUSTER_3:9440",
}

def api_request(host, method, url, payload=None):
    context = ssl._create_unverified_context()
    conn = http.client.HTTPSConnection(host, context=context)
    headers = {"Accept":"application/json", "Authorization":PE_AND_PC_TOKEN, "Content-Type":"application/json"}
    body = json.dumps(payload) if isinstance(payload, dict) else payload
    conn.request(method, url, body=body, headers=headers)
    res = conn.getresponse(); raw = res.read().decode("utf-8")
    try: data = json.loads(raw) if raw else {}
    except json.JSONDecodeError: data = {"raw": raw}
    if res.status >= 400: raise RuntimeError(f"API error {res.status} on {host}{url}: {data}")
    return data

def parse_dt(v):
    if not v: return None
    if isinstance(v,(int,float)):
        n=float(v); return datetime.fromtimestamp(n/1000000 if n>10000000000000 else n/1000 if n>10000000000 else n, tz=timezone.utc)
    if isinstance(v,str):
        t=v.strip().replace("Z","+00:00")
        try:
            d=datetime.fromisoformat(t); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError: return None
    return None

def list_vms():
    out=[]; off=0
    while True:
        d=api_request(NTNX_PRISMCENTRAL_IP,"POST","/api/nutanix/v3/vms/list",{"kind":"vm","length":100,"offset":off})
        e=d.get("entities",[])
        if not e: break
        out+=e; off+=100
        total=d.get("metadata",{}).get("total_matches")
        if total is not None and off>=total: break
    return out

def get_vm_by_name(name):
    for vm in list_vms():
        if vm.get("spec",{}).get("name")==name or vm.get("status",{}).get("name")==name: return vm
    return None

def get_vm(uuid): return api_request(NTNX_PRISMCENTRAL_IP,"GET",f"/api/nutanix/v3/vms/{uuid}")
def cluster_uuid(vm): return vm.get("status",{}).get("cluster_reference",{}).get("uuid") or vm.get("spec",{}).get("cluster_reference",{}).get("uuid")

def response_items(d):
    if isinstance(d.get("data"), list): return d["data"]
    if isinstance(d.get("data"), dict):
        for k in ("entities","items","recoveryPoints","snapshots"):
            if isinstance(d["data"].get(k), list): return d["data"][k]
    for k in ("entities","items","recoveryPoints","snapshots"):
        if isinstance(d.get(k), list): return d[k]
    return []

def list_recovery_points(): return response_items(api_request(NTNX_PRISMCENTRAL_IP,"GET","/api/dataprotection/v4.0/config/recovery-points"))
def list_snapshots(pe): return response_items(api_request(pe,"GET","/api/nutanix/v2.0/snapshots/"))
def obj_name(x): return x.get("name") or x.get("snapshot_name") or x.get("displayName") or (x.get("metadata") or {}).get("name") or (x.get("data") or {}).get("name") if isinstance(x.get("data"),dict) else None
def obj_id(x): return x.get("extId") or x.get("uuid") or x.get("id") or x.get("snapshot_uuid") or (x.get("metadata") or {}).get("uuid")
def created(x):
    sources=[x, x.get("metadata") if isinstance(x.get("metadata"),dict) else {}, x.get("data") if isinstance(x.get("data"),dict) else {}]
    for src in sources:
        for f in ("creationTime","createdTime","createdAt","creation_time","created_time","created_time_usecs"):
            d=parse_dt(src.get(f));
            if d: return d
    return None

def verify(items, kind, vm_name, vm_uuid, max_age, name_filter=None, pe_host=None):
    threshold=datetime.now(timezone.utc)-timedelta(hours=max_age); results=[]
    for item in items:
        text=json.dumps(item,ensure_ascii=False).lower(); name=obj_name(item)
        if name_filter and name_filter.lower() not in str(name or "").lower(): continue
        if vm_name.lower() not in text and vm_uuid.lower() not in text: continue
        c=created(item); results.append({"kind":kind,"name":name,"id":obj_id(item),"vm_name":vm_name,"vm_uuid":vm_uuid,"pe_host":pe_host,"created_at":c.isoformat() if c else None,"valid": bool(c and c>=threshold)})
    return results

def main():
    p=argparse.ArgumentParser(description="Verify recent Nutanix recovery points and Prism Element snapshots for a VM.")
    p.add_argument("--vm",required=True); p.add_argument("--mode",required=True,choices=["recovery","snapshot","both"]); p.add_argument("--max-age-hours",type=int,default=24); p.add_argument("--name-contains"); p.add_argument("--json-file")
    a=p.parse_args(); vm=get_vm_by_name(a.vm)
    if not vm: raise RuntimeError(f"VM '{a.vm}' was not found.")
    vm_uuid=vm.get("metadata",{}).get("uuid"); full=get_vm(vm_uuid); results=[]
    if a.mode in ("recovery","both"): results += verify(list_recovery_points(),"recovery_point",a.vm,vm_uuid,a.max_age_hours,a.name_contains)
    if a.mode in ("snapshot","both"):
        pe=PE_HOSTS_BY_CLUSTER_UUID.get(cluster_uuid(full))
        if not pe: raise RuntimeError("No Prism Element host configured for this VM cluster.")
        results += verify(list_snapshots(pe),"snapshot",a.vm,vm_uuid,a.max_age_hours,a.name_contains,pe)
    print(json.dumps(results,indent=2,ensure_ascii=False))
    if a.json_file: open(a.json_file,"w",encoding="utf-8").write(json.dumps(results,indent=2,ensure_ascii=False))
    if not any(r.get("valid") for r in results): raise SystemExit(1)
if __name__=="__main__": main()
