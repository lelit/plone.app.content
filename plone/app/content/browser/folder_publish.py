from plone.protect import CheckAuthenticator
from plone.protect import PostOnly
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as _
from Products.CMFPlone.utils import transaction_note
from ZODB.POSException import ConflictError
from zope.publisher.browser import BrowserView

import transaction


class FolderPublishView(BrowserView):
    """Publish objects from a folder.

    Originally: Products/CMFPlone/skins/plone_scripts/folder_publish.cpy
    Called by content_status_history, in plone.app.content.
    """

    def __call__(
        self,
        workflow_action=None,
        paths=None,
        comment="No comment",
        expiration_date=None,
        effective_date=None,
        include_children=False,
    ):
        # Use plone.protect.
        PostOnly(self.request)
        CheckAuthenticator(self.request)

        plone_utils = getToolByName(self.context, "plone_utils")
        if workflow_action is None:
            plone_utils.addPortalMessage(
                _("You must select a publishing action."), "error"
            )
            return self.redirect()
        if not paths:
            plone_utils.addPortalMessage(
                _("You must select content to change."), "error"
            )
            return self.redirect()

        self.transition_objects_by_paths(
            workflow_action,
            paths,
            comment,
            expiration_date,
            effective_date,
            include_children,
        )

        transaction_note(str(paths) + " transitioned " + workflow_action)
        plone_utils.addPortalMessage(_("Item state changed."))
        return self.redirect()

    def transition_objects_by_paths(
        self,
        workflow_action,
        paths,
        comment="",
        expiration_date=None,
        effective_date=None,
        include_children=False,
        handle_errors=True,
    ):
        """Originally this was in plone_utils.transitionObjectsByPaths.

        This was deprecated since 2015, so we copied it here.
        """
        failure = {}
        # use the portal for traversal in case we have relative paths
        portal = getToolByName(self, "portal_url").getPortalObject()
        traverse = portal.restrictedTraverse
        for path in paths:
            sp = transaction.savepoint(optimistic=True)
            try:
                obj = traverse(path, None)
                if obj is not None:
                    obj.content_status_modify(
                        workflow_action,
                        comment,
                        effective_date=effective_date,
                        expiration_date=expiration_date,
                    )
            except (ConflictError, KeyboardInterrupt):
                raise
            except Exception as e:
                # skip this object but continue with sub-objects.
                sp.rollback()
                failure[path] = e
            if getattr(obj, "isPrincipiaFolderish", None) and include_children:
                subobject_paths = [f"{path}/{id}" for id in obj]
                self.transition_objects_by_paths(
                    workflow_action,
                    subobject_paths,
                    comment,
                    expiration_date,
                    effective_date,
                    include_children,
                )
        return failure

    def redirect(self):
        target = self.request.get("orig_template", "")
        if target and not getToolByName(self.context, "portal_url").isURLInPortal(target):
            target = ""
        if not target:
            target = self.context.absolute_url()
        self.request.response.redirect(target)
