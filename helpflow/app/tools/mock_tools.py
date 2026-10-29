import json
from pathlib import Path
from app.database import SessionLocal, TicketRow
from app.config import settings

def _read(name):
    with (Path(settings.data_dir) / 'mock' / name).open(encoding='utf-8') as f:
        return json.load(f)
def check_service_status(service_name): return {'service_name':service_name,**_read('system_status.json').get(service_name.lower(),{'status':'unknown','uptime':'unknown','recent_restart':None})}
def search_logs(service_name,time_range='24h'): return {'service_name':service_name,'time_range':time_range,'entries':_read('logs.json').get(service_name.lower(),[])}
def find_runbook(issue_type):
    files={'payment':'payment-service-runbook.md','database':'database-troubleshooting.md','authentication':'authentication-runbook.md','notification':'notification-service-runbook.md','api':'api-500-errors.md'}
    name=files.get(issue_type.lower(),'incident-severity-guide.md'); path=Path(settings.data_dir) / 'documents' / name
    return {'runbook_title':name,'source_document':str(path),'content':path.read_text(encoding='utf-8')}
def get_recent_incidents(service_name): return {'service_name':service_name,'previous_incidents':_read('incidents.json').get(service_name.lower(),[])}
def create_ticket(title,description,priority):
    with SessionLocal() as db:
        row=TicketRow(title=title,description=description,service_name='unknown',status='OPEN',priority=priority); db.add(row); db.commit(); db.refresh(row); return {'ticket_id':row.id,'status':row.status}
def draft_customer_response(ticket_id,resolution): return {'ticket_id':ticket_id,'draft':resolution,'sent':False}
def request_sensitive_action(action_description): return {'requires_approval':True,'status':'PENDING','action_description':action_description}
