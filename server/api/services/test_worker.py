import sys
import pytest
import asyncio
from server.api.services import worker
from unittest.mock import MagicMock, patch

# Patch sys.modules to allow import of process_jobs_worker from worker.py
with patch.dict(
    sys.modules,
    {
        "services.logger": MagicMock(),
        "routers.frontal": MagicMock(),
        "models.crop_model": MagicMock(),
        "drivers.database": MagicMock(),
        "services.metrics": MagicMock(),
        "exlib.pyc.image_processor": MagicMock(),
        "exlib.py.image_processor": MagicMock(),
    },
):

    @pytest.mark.asyncio
    async def test_process_jobs_worker_job_not_found(monkeypatch) -> None:
        # Setup
        job_queue = asyncio.Queue()
        await job_queue.put("job1")

        # Mock DB session and model
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.first.return_value = None
        db_session_factory = MagicMock(return_value=db_session)
        db_crop_job_model = MagicMock()

        # Patch metrics and logger
        monkeypatch.setattr(worker, "job_total_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_failed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_completed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(
            worker, "job_processing_duration_seconds", MagicMock(observe=MagicMock())
        )
        monkeypatch.setattr(worker, "console", MagicMock())

        # Patch process_image_data_intensive to not be called
        monkeypatch.setattr(worker, "process_image_data_intensive", MagicMock())

        # Run worker for one iteration (it will continue forever, so we cancel after one)
        task = asyncio.create_task(
            worker.process_jobs_worker(
                job_queue,
                db_session_factory,
                db_crop_job_model,
                loadtest_mode_enabled=True,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Assert job_failed_counter was incremented
        assert worker.job_failed_counter.inc.called

    @pytest.mark.asyncio
    async def test_process_jobs_worker_job_already_completed(monkeypatch) -> None:
        job_queue = asyncio.Queue()
        await job_queue.put("job2")

        db_job = MagicMock()
        db_job.status = "completed"
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.first.return_value = db_job
        db_session_factory = MagicMock(return_value=db_session)
        db_crop_job_model = MagicMock()

        monkeypatch.setattr(worker, "job_total_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_failed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_completed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(
            worker, "job_processing_duration_seconds", MagicMock(observe=MagicMock())
        )
        monkeypatch.setattr(worker, "console", MagicMock())
        monkeypatch.setattr(worker, "process_image_data_intensive", MagicMock())

        task = asyncio.create_task(
            worker.process_jobs_worker(
                job_queue,
                db_session_factory,
                db_crop_job_model,
                loadtest_mode_enabled=True,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert worker.job_completed_counter.inc.called

    @pytest.mark.asyncio
    async def test_process_jobs_worker_success(monkeypatch) -> None:
        job_queue = asyncio.Queue()
        await job_queue.put("job3")

        db_job = MagicMock()
        db_job.status = "pending"
        db_job.landmarks_json = {"foo": "bar"}
        db_job.image_base64 = "abc123"
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.first.return_value = db_job
        db_session_factory = MagicMock(return_value=db_session)
        db_crop_job_model = MagicMock()

        monkeypatch.setattr(worker, "job_total_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_failed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_completed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(
            worker, "job_processing_duration_seconds", MagicMock(observe=MagicMock())
        )
        monkeypatch.setattr(worker, "console", MagicMock())
        process_image_mock = MagicMock(
            return_value=("svgbase64", ["contour1", "contour2"])
        )
        monkeypatch.setattr(worker, "process_image_data_intensive", process_image_mock)

        task = asyncio.create_task(
            worker.process_jobs_worker(
                job_queue,
                db_session_factory,
                db_crop_job_model,
                loadtest_mode_enabled=True,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check that process_image_data_intensive was called
        assert process_image_mock.called
        # Check that job_completed_counter was incremented
        assert worker.job_completed_counter.inc.called
        # Check that db_job status was set to completed
        assert db_job.status == "completed"

    @pytest.mark.asyncio
    async def test_process_jobs_worker_exception(monkeypatch) -> None:
        job_queue = asyncio.Queue()
        await job_queue.put("job4")

        db_job = MagicMock()
        db_job.status = "pending"
        db_job.landmarks_json = {"foo": "bar"}
        db_job.image_base64 = "abc123"
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.first.return_value = db_job
        db_session_factory = MagicMock(return_value=db_session)
        db_crop_job_model = MagicMock()

        monkeypatch.setattr(worker, "job_total_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_failed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(worker, "job_completed_counter", MagicMock(inc=MagicMock()))
        monkeypatch.setattr(
            worker, "job_processing_duration_seconds", MagicMock(observe=MagicMock())
        )
        monkeypatch.setattr(worker, "console", MagicMock())
        # Raise exception in process_image_data_intensive
        monkeypatch.setattr(
            worker,
            "process_image_data_intensive",
            MagicMock(side_effect=Exception("fail")),
        )

        task = asyncio.create_task(
            worker.process_jobs_worker(
                job_queue,
                db_session_factory,
                db_crop_job_model,
                loadtest_mode_enabled=True,
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check that job_failed_counter was incremented
        assert worker.job_failed_counter.inc.called
        # Check that db_job status was set to failed
        assert db_job.status == "failed"

    @pytest.mark.asyncio
    async def test_startup_and_shutdown_worker(monkeypatch) -> None:
        # Mock app_instance
        class State:
            pass

        class App:
            state = State()

        app_instance = App()

        monkeypatch.setattr(worker, "Base", MagicMock())
        monkeypatch.setattr(worker, "engine", MagicMock())
        monkeypatch.setattr(worker, "job_queue", asyncio.Queue())
        monkeypatch.setattr(worker, "SessionLocal", MagicMock())
        monkeypatch.setattr(worker, "DBCropJob", MagicMock())
        monkeypatch.setattr(worker, "console", MagicMock())

        # Patch asyncio.create_task to return a dummy task
        dummy_task = MagicMock()
        monkeypatch.setattr(asyncio, "create_task", MagicMock(return_value=dummy_task))

        # Test startup
        await worker.startup_db_and_worker(app_instance, loadtest_mode_enabled=True)
        assert hasattr(app_instance.state, "job_processing_task")

        # Test shutdown
        dummy_task.cancel = MagicMock()
        dummy_task.__await__ = lambda s: iter([])
        await worker.shutdown_worker(app_instance)
        assert dummy_task.cancel.called
