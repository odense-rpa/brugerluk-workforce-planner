import logging
import sys

from automation_server_client import (
    AutomationServer,
    Workqueue,
    Credential,
    WorkItemStatus,
)
from boss_client import client as boss_client
from odk_tools.reporting import report
from odk_tools.tracking import Tracker
from workforce_planner_client.client import WorkforcePlannerClient

proces_navn = "Brugerluk WorkForce Planner"


def populate_queue(workqueue: Workqueue, boss: boss_client.BossClient):
    logger = logging.getLogger(__name__)
    systems = boss.hent_systemer()
    boss_items = [item for item in systems["systems"] if item["systemName"] == "WorkForce Planner"]

    for item in boss_items:
        workqueue.add_item(item, item["initials"])


def process_workqueue(
    workqueue: Workqueue,
    boss: boss_client.BossClient,
    workforce_planner: WorkforcePlannerClient,
    tracker: Tracker,
):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict

            try:
                workforce_planner.slet_personressource(data["email"])
                workforce_planner.deaktiver_bruger(data["email"])
                boss.marker_bruger_som_slettet(data["id"])
                tracker.track_task(proces_navn)
            except ValueError as e:
                report(
                    "brugerluk_workforce_planner",
                    "Fejl",
                    {"Brugernavn": data["initials"], "Fejl": str(e)},
                )
                boss.marker_bruger_som_slettet(data["id"])
                tracker.track_partial_task(proces_navn)


if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    tracking_credential = Credential.get_credential("Odense SQL Server")
    boss_credential = Credential.get_credential("BOSS")
    robob_credential = Credential.get_credential("RoboB")

    boss = boss_client.BossClient(
        client_id=boss_credential.username,
        client_secret=boss_credential.password,
        api_url=boss_credential.data["api_url"],
        base_url=boss_credential.data["base_url"],
        login_url=boss_credential.data["login_url"],
    )

    workforce_planner = WorkforcePlannerClient(
        base_url=robob_credential.data["workforce_planner_url"],
        username=robob_credential.username,
        password=robob_credential.password,
        headless=False
    )

    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        populate_queue(workqueue, boss)
        exit(0)

    # Process workqueue
    process_workqueue(workqueue, boss, workforce_planner, tracker)