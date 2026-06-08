using UnityEngine;

public class HUDManager : MonoBehaviour
{
    public string heroName = "\u961f\u957f";

    private PlayerHealth player;
    private WeaponController weapons;
    private Texture2D portrait;

    void Start()
    {
        player = Object.FindFirstObjectByType<PlayerHealth>();
        weapons = Object.FindFirstObjectByType<WeaponController>();
        portrait = Resources.Load<Texture2D>("HeroPortrait");
    }

    void OnGUI()
    {
        DrawDamageFlash();

        GUIStyle label = new GUIStyle(GUI.skin.label);
        label.fontSize = 22;
        label.normal.textColor = Color.white;

        DrawHeroPortrait();
        DrawWeaponInfo(label);
        DrawHealth(label);
        DrawHitMarker();
        DrawProtectionHint(label);
        DrawGameState(label);
    }

    private void DrawDamageFlash()
    {
        if (player == null || Time.time - player.LastDamageTime >= 0.3f)
            return;

        float alpha = Mathf.Clamp01(1f - (Time.time - player.LastDamageTime) / 0.3f) * 0.4f;
        Color oldColor = GUI.color;
        GUI.color = new Color(1f, 0f, 0f, alpha);
        GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
        GUI.color = oldColor;
    }

    private void DrawHeroPortrait()
    {
        if (portrait == null)
            return;

        GUI.DrawTexture(new Rect(20, 20, 64, 64), portrait, ScaleMode.ScaleToFit);
        GUIStyle nameStyle = new GUIStyle(GUI.skin.label);
        nameStyle.fontSize = 16;
        nameStyle.normal.textColor = Color.white;
        GUI.Label(new Rect(92, 28, 260, 24), "\u7279\u79cd\u90e8\u961f\u961f\u957f", nameStyle);
        GUI.Label(new Rect(92, 50, 260, 24), heroName, nameStyle);
    }

    private void DrawWeaponInfo(GUIStyle label)
    {
        if (weapons == null)
            return;

        GUI.Label(new Rect(20, Screen.height - 138, 420, 30), "\u6b66\u5668: " + weapons.CurrentWeaponName, label);

        if (weapons.IsGrenadeSelected)
            GUI.Label(new Rect(20, Screen.height - 110, 420, 30), "\u6295\u63b7: \u624b\u96f7", label);
        else
            GUI.Label(new Rect(20, Screen.height - 110, 420, 30), "\u5f39\u836f: " + weapons.CurrentMag + " / " + weapons.CurrentReserve, label);

        GUI.Label(new Rect(20, Screen.height - 82, 420, 30), "\u624b\u96f7: " + weapons.GrenadeCount, label);
    }

    private void DrawHealth(GUIStyle label)
    {
        if (player == null)
            return;

        GUI.Label(new Rect(20, Screen.height - 54, 420, 30), "\u751f\u547d: " + Mathf.Ceil(player.Current) + " / " + player.Max, label);

        Rect back = new Rect(20, Screen.height - 22, 220, 10);
        Color old = GUI.color;
        GUI.color = new Color(0f, 0f, 0f, 0.45f);
        GUI.DrawTexture(back, Texture2D.whiteTexture);
        GUI.color = Color.Lerp(new Color(0.95f, 0.18f, 0.12f), new Color(0.2f, 0.85f, 0.35f), player.Current / Mathf.Max(1f, player.Max));
        GUI.DrawTexture(new Rect(back.x, back.y, back.width * player.Current / Mathf.Max(1f, player.Max), back.height), Texture2D.whiteTexture);
        GUI.color = old;
    }

    private void DrawHitMarker()
    {
        if (weapons == null || Time.time - weapons.LastHitTime > 0.18f)
            return;

        float alpha = Mathf.Clamp01(1f - (Time.time - weapons.LastHitTime) / 0.18f);
        GUIStyle style = new GUIStyle(GUI.skin.label);
        style.fontSize = 34;
        style.alignment = TextAnchor.MiddleCenter;
        style.normal.textColor = new Color(1f, 1f, 1f, alpha);
        GUI.Label(new Rect(Screen.width / 2 - 45, Screen.height / 2 - 46, 90, 90), "X", style);
    }

    private void DrawProtectionHint(GUIStyle label)
    {
        if (player == null || !player.IsProtected)
            return;

        GUIStyle hint = new GUIStyle(label);
        hint.fontSize = 18;
        hint.alignment = TextAnchor.MiddleCenter;
        hint.normal.textColor = new Color(0.55f, 0.9f, 1f);
        GUI.Label(new Rect(0, Screen.height - 90, Screen.width, 28), "\u8bad\u7ec3\u9632\u62a4\u4e2d", hint);
    }

    private void DrawGameState(GUIStyle label)
    {
        if (GameManager.Instance == null)
            return;

        GUI.Label(new Rect(Screen.width - 240, 20, 220, 30),
            "\u51fb\u6740: " + GameManager.Instance.Kills + " / " + GameManager.Instance.killsToWin, label);

        if (GameManager.Instance.CurrentState == GameManager.State.Playing)
            return;

        bool won = GameManager.Instance.CurrentState == GameManager.State.Won;

        GUIStyle big = new GUIStyle(GUI.skin.label);
        big.fontSize = 64;
        big.alignment = TextAnchor.MiddleCenter;
        big.normal.textColor = won ? new Color(0.78f, 0.9f, 0.25f) : new Color(0.9f, 0.35f, 0.2f);
        GUI.Label(new Rect(0, Screen.height / 2 - 90, Screen.width, 110), won ? "\u80dc\u5229!" : "\u4efb\u52a1\u5931\u8d25", big);

        GUIStyle hint = new GUIStyle(GUI.skin.label);
        hint.fontSize = 26;
        hint.alignment = TextAnchor.MiddleCenter;
        hint.normal.textColor = Color.white;
        GUI.Label(new Rect(0, Screen.height / 2 + 30, Screen.width, 40), "\u6309 R \u91cd\u65b0\u5f00\u59cb", hint);
    }
}
