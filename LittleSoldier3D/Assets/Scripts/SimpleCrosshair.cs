using UnityEngine;

public class SimpleCrosshair : MonoBehaviour
{
    public float size = 6f;
    public Color color = Color.white;

    private void OnGUI()
    {
        float x = (Screen.width - size) / 2f;
        float y = (Screen.height - size) / 2f;
        Color old = GUI.color;
        GUI.color = color;
        GUI.DrawTexture(new Rect(x, y, size, size), Texture2D.whiteTexture);
        GUI.color = old;
    }
}
