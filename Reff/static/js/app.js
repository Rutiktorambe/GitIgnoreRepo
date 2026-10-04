let employees=[],jobs=[],referrals=[];

document.addEventListener("DOMContentLoaded",async()=>{await loadEmployees();await loadJobs();await loadReferrals();setupEvents();});

async function loadEmployees(){
 const r=await fetch("/api/employees"); employees=await r.json();
 const s=document.getElementById("employee");
 s.innerHTML='<option value="">Select Employee</option>';
 employees.forEach(e=>{const o=document.createElement("option");o.value=e.id;o.textContent=`${e.employee_code} - ${e.name}`;s.appendChild(o);});
}

async function loadJobs(){
 const r=await fetch("/api/jobs"); jobs=await r.json();
 const s=document.getElementById("jobRole");
 s.innerHTML='<option value="">Select Job</option>';
 jobs.forEach(j=>{const o=document.createElement("option");o.value=j.id;o.textContent=`${j.role_name} - ${j.category}`;s.appendChild(o);});
}

async function loadReferrals(){
 const r=await fetch("/api/referrals"); referrals=await r.json();
 renderReferrals(referrals); updateDashboard();
}

function handleEmployeeChange(){
 const e=employees.find(x=>x.id===Number(document.getElementById("employee").value));
 document.getElementById("employeeTeam").value=e?e.team:"";
}

function handleJobChange(){
 const j=jobs.find(x=>x.id===Number(document.getElementById("jobRole").value));
 const loc=document.getElementById("jobLocation"), rs=document.getElementById("requirementsSection");
 const list=document.getElementById("requirementsList"), as=document.getElementById("actuarialSection");
 const exam=document.getElementById("actuarialExam"), help=document.getElementById("examHelp");
 if(!j){loc.value="";rs.classList.add("hidden");as.classList.add("hidden");return}
 loc.value=j.location||"";list.innerHTML="";
 j.requirements.forEach(r=>{
  const d=document.createElement("div");d.className="requirement-item";
  d.innerHTML=`<div><strong>${r.name}</strong><div>${r.description||""}</div></div><span class="badge ${r.mandatory?"mandatory":"optional"}">${r.mandatory?"Mandatory":"Optional"}</span>`;
  list.appendChild(d);
 });
 rs.classList.toggle("hidden",j.requirements.length===0);
 if(j.actuarial_exam_required||j.actuarial_exam_optional){
  as.classList.remove("hidden");exam.required=j.actuarial_exam_required;
  help.textContent=j.actuarial_exam_required?"Actuarial exam information is mandatory for this role.":"Actuarial exam information is optional for this role.";
 }else{as.classList.add("hidden");exam.required=false;exam.value=""}
}

async function submitReferral(e){
 e.preventDefault();
 const payload={
  employee_id:document.getElementById("employee").value,
  job_role_id:document.getElementById("jobRole").value,
  candidate_name:document.getElementById("candidateName").value,
  candidate_email:document.getElementById("candidateEmail").value,
  candidate_phone:document.getElementById("candidatePhone").value,
  candidate_experience:document.getElementById("experience").value,
  actuarial_exam:document.getElementById("actuarialExam").value
 };
 const r=await fetch("/api/referrals",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
 const data=await r.json(),msg=document.getElementById("message");
 msg.textContent=data.message;msg.className=data.success?"message success":"message error";
 if(data.success){document.getElementById("referralForm").reset();document.getElementById("employeeTeam").value="";document.getElementById("jobLocation").value="";document.getElementById("requirementsSection").classList.add("hidden");document.getElementById("actuarialSection").classList.add("hidden");await loadReferrals();}
}

function renderReferrals(data){
 const t=document.getElementById("referralTable");t.innerHTML="";
 data.forEach(r=>{const tr=document.createElement("tr");tr.innerHTML=`<td>${r.id}</td><td>${r.employee}<br><small>${r.employee_code}</small></td><td>${r.team}</td><td>${r.candidate_name}</td><td>${r.candidate_email}</td><td>${r.job}</td><td>${r.category}</td><td>${r.experience||"-"}</td><td>${r.actuarial_exam||"-"}</td><td>${r.referral_date}</td><td><span class="status">${r.status}</span></td>`;t.appendChild(tr);});
}

function updateDashboard(){
 const total=referrals.length,a=referrals.filter(r=>r.category==="Actuarial").length,t=referrals.filter(r=>r.category==="Technical").length;
 document.getElementById("totalReferrals").textContent=total;
 document.getElementById("actuarialReferrals").textContent=a;
 document.getElementById("technicalReferrals").textContent=t;
 document.getElementById("otherReferrals").textContent=total-a-t;
}

function searchReferrals(){
 const q=document.getElementById("search").value.toLowerCase();
 renderReferrals(referrals.filter(r=>[r.employee,r.candidate_name,r.candidate_email,r.job,r.team].some(v=>(v||"").toLowerCase().includes(q))));
}

function setupEvents(){
 document.getElementById("employee").addEventListener("change",handleEmployeeChange);
 document.getElementById("jobRole").addEventListener("change",handleJobChange);
 document.getElementById("referralForm").addEventListener("submit",submitReferral);
 document.getElementById("search").addEventListener("input",searchReferrals);
}
