# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from airflow.api_connexion import security
from airflow.api_connexion.exceptions import NotFound
from airflow.api_connexion.parameters import apply_sorting, check_limit, format_parameters
from airflow.api_connexion.schemas.event_log_schema import (
    EventLogCollection,
    event_log_collection_schema,
    event_log_schema,
)
from airflow.auth.managers.models.resource_details import DagAccessEntity
from airflow.models import Log
from airflow.utils import timezone
from airflow.utils.db import get_query_count
from airflow.utils.session import NEW_SESSION, provide_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from airflow.api_connexion.types import APIResponse


@security.requires_access_dag("GET", DagAccessEntity.AUDIT_LOG)
@provide_session
def get_event_log(*, event_log_id: int, session: Session = NEW_SESSION) -> APIResponse:
    """Get a log entry."""
    event_log = session.get(Log, event_log_id)
    if event_log is None:
        raise NotFound("Event Log not found")
    return event_log_schema.dump(event_log)


@security.requires_access_dag("GET", DagAccessEntity.AUDIT_LOG)
@format_parameters({"limit": check_limit})
@provide_session
def get_event_logs(
    *,
    dag_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    map_index: int | None = None,
    try_number: int | None = None,
    owner: str | None = None,
    event: str | None = None,
    excluded_events: str | None = None,
    included_events: str | None = None,
    before: str | None = None,
    after: str | None = None,
    limit: int,
    offset: int | None = None,
    order_by: str = "event_log_id",
    session: Session = NEW_SESSION,
) -> APIResponse:
    """Get all log entries from event log."""
    to_replace = {"event_log_id": "id", "when": "dttm"}
    allowed_sort_attrs = [
        "event_log_id",
        "when",
        "dag_id",
        "task_id",
        "run_id",
        "event",
        "execution_date",
        "owner",
        "extra",
    ]
    query = select(Log)

    if dag_id:
        query = query.where(Log.dag_id == dag_id)
    if task_id:
        query = query.where(Log.task_id == task_id)
    if run_id:
        query = query.where(Log.run_id == run_id)
    if map_index:
        query = query.where(Log.map_index == map_index)
    if try_number:
        query = query.where(Log.try_number == try_number)
    if owner:
        query = query.where(Log.owner == owner)
    if event:
        query = query.where(Log.event == event)
    if included_events:
        included_events_list = included_events.split(",")
        query = query.where(Log.event.in_(included_events_list))
    if excluded_events:
        excluded_events_list = excluded_events.split(",")
        query = query.where(Log.event.notin_(excluded_events_list))
    if before:
        query = query.where(Log.dttm < timezone.parse(before))
    if after:
        query = query.where(Log.dttm > timezone.parse(after))

    total_entries = get_query_count(query, session=session)

    query = apply_sorting(query, order_by, to_replace, allowed_sort_attrs)
    event_logs = session.scalars(query.offset(offset).limit(limit)).all()
    return event_log_collection_schema.dump(
        EventLogCollection(event_logs=event_logs, total_entries=total_entries)
    )
