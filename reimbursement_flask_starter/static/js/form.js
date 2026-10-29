(function(){
const container=document.getElementById('rows'), add=document.getElementById('add-row'), tpl=document.getElementById('row-template');
function renumber(){[...container.querySelectorAll('.row')].forEach((r,i)=>{r.querySelector('.rowhead strong').textContent='Expense entry '+(i+1);r.querySelector('input[name="Item[]"]').value=i+1;const attachments=r.querySelector('input[type="file"]');if(attachments)attachments.name='attachments_'+i;syncCode(r);});totals();}
function syncCode(row){const desc=row.querySelector('.description-select');const code=row.querySelector('.gcc-code');if(desc&&code){const codes = JSON.parse(document.getElementById("gcc-code-map").textContent);code.value=codes[desc.value]||'';}}
container.addEventListener('change',e=>{if(e.target.matches('.description-select'))syncCode(e.target.closest('.row'));});
function totals(){let b=0,c=0;document.querySelectorAll('.bill').forEach(x=>b+=parseFloat(x.value)||0);document.querySelectorAll('.claim').forEach(x=>c+=parseFloat(x.value)||0);document.getElementById('bill-total').textContent='₹'+b.toFixed(2);document.getElementById('claim-total').textContent='₹'+c.toFixed(2);}
add.addEventListener('click',()=>{container.appendChild(tpl.content.cloneNode(true));renumber();});
container.addEventListener('click',e=>{if(!e.target.classList.contains('remove-row'))return;if(container.querySelectorAll('.row').length<=1){alert('At least one expense entry is required.');return;}e.target.closest('.row').remove();renumber();});
container.addEventListener('input',e=>{if(e.target.matches('.bill,.claim'))totals();});
renumber();
})();
