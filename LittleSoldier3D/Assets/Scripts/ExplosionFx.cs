using UnityEngine;

public class ExplosionFx : MonoBehaviour
{
    private float maxRadius;
    private float t;
    private const float Duration = 0.18f;

    public void Init(float radius)
    {
        maxRadius = radius;
        transform.localScale = Vector3.zero;
    }

    void Update()
    {
        t += Time.deltaTime;
        float k = Mathf.Clamp01(t / Duration);
        transform.localScale = Vector3.one * (maxRadius * 2f * k);
        if (t >= Duration)
            Destroy(gameObject);
    }
}
