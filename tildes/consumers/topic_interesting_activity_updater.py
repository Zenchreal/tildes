# Copyright (c) 2019 Tildes contributors <code@tildes.net>
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Consumer that updates topics' last_interesting_activity_time."""

from datetime import datetime
from typing import Optional

from tildes.enums import CommentTreeSortOption
from tildes.lib.event_stream import EventStreamConsumer, Message
from tildes.models.comment import Comment, CommentInTree, CommentTree


class TopicInterestingActivityUpdater(EventStreamConsumer):
    """Consumer that updates topics' last_interesting_activity_time."""

    def process_message(self, message: Message) -> None:
        """Process a message from the stream."""
        trigger_comment = (
            self.db_session.query(Comment)
            .filter_by(comment_id=message.fields["comment_id"])
            .one()
        )

        topic = trigger_comment.topic

        all_comments = self.db_session.query(Comment).filter_by(topic=topic).all()

        tree = CommentTree(all_comments, CommentTreeSortOption.NEWEST)

        # default the last interesting time to the topic's creation
        last_interesting_time = topic.created_time

        for comment in tree:
            branch_time = self._find_last_interesting_time(comment)
            if branch_time and branch_time > last_interesting_time:
                last_interesting_time = branch_time

        topic.last_interesting_activity_time = last_interesting_time

    def _find_last_interesting_time(self, comment: CommentInTree) -> Optional[datetime]:
        """Recursively find the last "interesting" time from a comment and replies."""
        # stop considering comments interesting once they get too deep down a branch
        if comment.depth >= 5:
            return None

        # if the comment has one of these labels, don't look any deeper down this branch
        uninteresting_labels = ("noise", "offtopic", "malice")
        if any(comment.is_label_active(label) for label in uninteresting_labels):
            return None

        # the comment itself isn't interesting if it's deleted or removed, but one of
        # its children still could be, so we still want to keep recursing under it
        if not (comment.is_deleted or comment.is_removed):
            comment_time = comment.created_time
        else:
            comment_time = None

        # find the max interesting time from all of this comment's replies
        reply_time = None
        if comment.replies:
            reply_times = [
                self._find_last_interesting_time(reply) for reply in comment.replies
            ]
            try:
                reply_time = max([time for time in reply_times if time])
            except ValueError:
                # all reply_times were None, just fall through
                pass

        # disregard either time if it's None (or both)
        potential_times = [time for time in (comment_time, reply_time) if time]

        if potential_times:
            return max(potential_times)

        # will only be reached if both the comment and reply times were None
        return None


if __name__ == "__main__":
    TopicInterestingActivityUpdater(
        "topic_interesting_activity_updater",
        source_streams=[
            "comments.insert",
            "comments.update.is_deleted",
            "comments.update.markdown",
            "comments.update.is_removed",
            "comment_labels.insert",
            "comment_labels.delete",
        ],
    ).consume_streams()
