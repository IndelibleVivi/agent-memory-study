"""Explicit HTTP/CLI dispatch to the same intake, review and publication owners."""
import base64
from urllib.parse import parse_qs

from .intake import CaptureService
from .identity import IdentityService
from .acquisition import AcquisitionService
from .arguments import ArgumentService
from .revisions import RevisionService
from .publication import PublicationService
from .repository import RepositoryError


class WorkspaceAPI:
    def __init__(self, repo, project, public_records):
        self.capture = CaptureService(repo, project, public_records)
        self.identity = IdentityService(repo, public_records)
        self.acquisition = AcquisitionService(repo, public_records)
        self.arguments = ArgumentService(repo, public_records)
        self.revisions = RevisionService(repo, project, public_records)
        # Preparing/reviewing a selection grants no Git or deployment authority.
        self.publication = PublicationService(repo, project, public_records)

    def handle(self, method, path, query, body):
        field = lambda name: parse_qs(query).get(name, [None])[0]
        if method == 'GET':
            if path == '/api/captures': return {'captures': self.capture.list()}
            if path == '/api/capture': return self.capture.get(field('id'))
            if path == '/api/acquisition': return self.acquisition.inspect(field('capture_id'))
            if path == '/api/revision/units': return {'units': self.revisions.units(field('id'))}
            if path == '/api/publication/site': return {'site': self.publication.current_site()}
        if method == 'POST':
            if path == '/api/capture/file':
                fields = dict(body)
                raw = base64.b64decode(fields.pop('base64'), validate=True)
                return self.capture.capture_bytes(raw=raw, **fields)
            if path == '/api/acquisition/file':
                fields = dict(body)
                raw = base64.b64decode(fields.pop('base64'), validate=True)
                return self.acquisition.execute_file(selected_bytes=raw, **fields)
            operations = {
                '/api/capture': self.capture.capture,
                '/api/capture/batch': self.capture.batch,
                '/api/capture/attention': self.capture.attention,
                '/api/capture/context': self.capture.context_links,
                '/api/identity/resolve': self.identity.resolve,
                '/api/identity/confirm': self.identity.confirm,
                '/api/identity/merge': self.identity.merge,
                '/api/identity/split': self.identity.split,
                '/api/acquisition/plan-url': self.acquisition.plan_url,
                '/api/acquisition/plan-file': self.acquisition.plan_file,
                '/api/acquisition/url': self.acquisition.execute_url,
                '/api/acquisition/cancel': self.acquisition.cancel,
                '/api/acquisition/extract': self.acquisition.extract,
                '/api/acquisition/read': self.acquisition.read_activity,
                '/api/acquisition/compare': self.acquisition.compare,
                '/api/acquisition/reanchor': self.acquisition.reanchor,
                '/api/argument/propose': self.arguments.propose,
                '/api/argument/accept': self.arguments.accept,
                '/api/argument/reject': self.arguments.reject,
                '/api/argument/bundle': self.arguments.bundle,
                '/api/argument/withdraw': self.arguments.withdraw,
                '/api/argument/impact': self.arguments.impact,
                '/api/argument/status': self.arguments.support_status,
                '/api/revision/create': self.revisions.create,
                '/api/revision/review': self.revisions.review,
                '/api/revision/pause': self.revisions.pause,
                '/api/revision/apply': self.revisions.apply_db,
                '/api/revision/prepare-git': self.revisions.prepare_git,
                '/api/revision/record-git': self.revisions.record_git_unit,
                '/api/publication/prepare': self.publication.prepare,
                '/api/publication/preview': self.publication.preview,
                '/api/publication/projection': self.publication.public_projection,
                '/api/publication/delivery': self.publication.record_delivery,
                '/api/publication/deliveries': self.publication.deliveries,
            }
            if path in operations:
                if not isinstance(body, dict): raise ValueError('操作需要明确 JSON 对象。')
                return operations[path](**body)
        raise RepositoryError('not-found', '没有这个本地操作。')
