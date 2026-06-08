using UnityEngine;
using UnityEngine.SceneManagement;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance;

    public int killsToWin = 5;
    public int Kills { get; private set; }

    public enum State { Playing, Won, Lost }
    public State CurrentState { get; private set; }

    void Awake()
    {
        Instance = this;
        Time.timeScale = 1f;
        CurrentState = State.Playing;
        Kills = 0;
    }

    public void AddKill()
    {
        if (CurrentState != State.Playing) return;
        Kills++;
        if (Kills >= killsToWin)
        {
            CurrentState = State.Won;
            EndGame();
        }
    }

    public void PlayerDied()
    {
        if (CurrentState != State.Playing) return;
        CurrentState = State.Lost;
        EndGame();
    }

    void EndGame()
    {
        Time.timeScale = 0f;
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
    }

    void Update()
    {
        if (CurrentState != State.Playing && Input.GetKeyDown(KeyCode.R))
        {
            Time.timeScale = 1f;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);
        }
    }
}
