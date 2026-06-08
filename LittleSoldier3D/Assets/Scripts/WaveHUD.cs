using UnityEngine;

public class WaveHUD : MonoBehaviour
{
    private WaveManager waveManager;

    void Start()
    {
        waveManager = Object.FindFirstObjectByType<WaveManager>();
    }

    void OnGUI()
    {
        if (waveManager == null)
            return;

        GUIStyle top = new GUIStyle(GUI.skin.label);
        top.fontSize = 22;
        top.alignment = TextAnchor.MiddleCenter;
        top.normal.textColor = Color.white;
        GUI.Label(new Rect(0, 16, Screen.width, 30),
            "\u7b2c " + waveManager.CurrentWave + " / " + waveManager.TotalWaves + " \u6ce2", top);

        if (Time.time < waveManager.BannerUntil)
        {
            GUIStyle banner = new GUIStyle(GUI.skin.label);
            banner.fontSize = 46;
            banner.alignment = TextAnchor.MiddleCenter;
            banner.normal.textColor = new Color(1f, 0.85f, 0.2f);
            GUI.Label(new Rect(0, Screen.height / 2 - 150, Screen.width, 70), waveManager.BannerText, banner);
        }
    }
}
