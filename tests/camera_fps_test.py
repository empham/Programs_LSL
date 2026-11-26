import cv2
import time


def test_camera_fps(
    camera_index=0,
    width=1280,
    height=720,
    requested_fps_list=(15, 30, 60),
    test_duration=5
):

    for requested_fps in requested_fps_list:

        print("\n--------------------------------")
        print(f"Testing {width}x{height} @ {requested_fps} FPS")

        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

        if not cap.isOpened():
            print("ERROR: Could not open camera.")
            return

        # Configure Camera

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, requested_fps)

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Actual Resolution: {actual_width}x{actual_height}")

        # Measure Actual FPS

        frame_count = 0

        start_time = time.perf_counter()

        while True:

            ret, frame = cap.read()

            if not ret:
                print("WARNING: Frame capture failed.")
                break

            frame_count += 1

            elapsed_time = (
                time.perf_counter()
                - start_time
            )

            cv2.imshow("FPS Test", frame)

            if elapsed_time >= test_duration:
                break

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        end_time = time.perf_counter()

        elapsed_time = end_time - start_time

        actual_fps = frame_count / elapsed_time

        print(f"Measured FPS: {actual_fps:.2f}")

        # Performance Evaluation

        fps_ratio = actual_fps / requested_fps

        if fps_ratio >= 0.95:
            print("Status: EXCELLENT")
        elif fps_ratio >= 0.80:
            print("Status: ACCEPTABLE")
        else:
            print("Status: POOR")

        cap.release()

        # Check if user wants to test next configuration
        print("\nPress 'n' to test next configuration or 'q' to quit.")
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key == ord("n"):
                break
            elif key == ord("q"):
                print("Exiting tests.")
                cv2.destroyAllWindows()
                return

    cv2.destroyAllWindows()


if __name__ == "__main__":

    test_camera_fps(
        camera_index=0,
        # width=1280,
        # height=720,
        # width=800,
        # height=600,
        width=640,
        height=480,
        requested_fps_list=[5, 7.5,10, 15, 30, 60],
        test_duration=5
    )


